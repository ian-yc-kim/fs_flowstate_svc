import asyncio
import json
import pytest
from types import SimpleNamespace

import fs_flowstate_svc.frontend.auth_utils as auth_utils
from fs_flowstate_svc.frontend import websocket_client


@pytest.mark.asyncio
async def test_build_ws_url_uses_token():
    url = websocket_client.build_ws_url("abc123", host="host.test", port=9000)
    assert "token=abc123" in url
    assert url.startswith("ws://host.test:9000/ws/sync")


class DummyWS:
    def __init__(self, recv_messages=None):
        self._send = []
        self._recv_messages = recv_messages or []
        self._closed = False

    async def send(self, payload: str):
        self._send.append(payload)

    async def recv(self):
        if not self._recv_messages:
            # simulate closed connection
            raise Exception("closed")
        return self._recv_messages.pop(0)

    async def close(self):
        self._closed = True


@pytest.mark.asyncio
async def test_reader_responds_to_ping_and_delivers_messages(monkeypatch):
    # prepare a dummy ws that will first send a ping, then a normal message, then close
    ping = json.dumps({"type": "ping", "payload": {}})
    msg = json.dumps({"type": "event_update", "payload": {"x": 1}})
    ws = DummyWS(recv_messages=[ping, msg])

    sent = []

    async def fake_send(payload: str):
        sent.append(payload)

    ws.send = fake_send

    collected = []

    async def on_message(data):
        collected.append(data)

    async def on_error(e):
        pytest.fail(f"on_error called: {e}")

    stop_event = asyncio.Event()

    # run reader loop until it raises/finishes
    await websocket_client.reader_loop(ws, on_message, on_error, stop_event)

    # after processing ping, a pong should have been sent
    assert any(json.loads(s).get("type") == "pong" for s in sent)
    # event_update delivered to on_message
    assert any(c.get("type") == "event_update" for c in collected)


@pytest.mark.asyncio
async def test_sender_sends_queue_items():
    ws = DummyWS()
    sent = []

    async def fake_send(payload: str):
        sent.append(payload)

    ws.send = fake_send

    q = asyncio.Queue()
    stop_event = asyncio.Event()

    # enqueue one message
    await q.put(websocket_client.make_ws_message("event_update", {"a": 1}))

    # run sender loop in background and cancel after a short wait
    task = asyncio.create_task(websocket_client.sender_loop(ws, q, stop_event))
    await asyncio.sleep(0.05)
    stop_event.set()
    await asyncio.wait_for(task, timeout=1.0)

    assert sent, "No messages were sent"
    parsed = json.loads(sent[0])
    assert parsed["type"] == "event_update"
    assert parsed["payload"]["a"] == 1


@pytest.mark.asyncio
async def test_connect_ws_uses_websockets(monkeypatch):
    # Patch websockets.connect to return our DummyWS
    dummy = DummyWS()

    class Fake:
        async def __call__(self, url):
            return dummy

    fake_connect = Fake()
    monkeypatch.setattr(websocket_client, "websockets", SimpleNamespace(connect=fake_connect))

    ws = await websocket_client.connect_ws("ws://localhost/ws/sync?token=tok", max_retries=1)
    assert ws is dummy
