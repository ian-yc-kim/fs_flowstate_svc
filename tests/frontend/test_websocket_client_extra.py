import asyncio
import json
import pytest
from types import SimpleNamespace

import fs_flowstate_svc.frontend.auth_utils as auth_utils
from fs_flowstate_svc.frontend import websocket_client


class DummyWSShort:
    """Simple Dummy WS that raises immediately on recv."""
    def __init__(self):
        self.sent = []

    async def send(self, payload: str):
        self.sent.append(payload)

    async def recv(self):
        raise Exception("boom")

    async def close(self):
        pass


class DummyWSSucceedsAfter:
    """Fake connect callable: fail first call then return dummy on second."""
    def __init__(self, dummy):
        self.calls = 0
        self.dummy = dummy

    async def __call__(self, url):
        self.calls += 1
        if self.calls == 1:
            raise Exception("temporary failure")
        return self.dummy


@pytest.mark.asyncio
async def test_connect_ws_retries_and_succeeds(monkeypatch):
    dummy = SimpleNamespace()

    fake = DummyWSSucceedsAfter(dummy)
    # monkeypatch the websockets namespace used by the module
    monkeypatch.setattr(websocket_client, "websockets", SimpleNamespace(connect=fake))

    # backoff_base=0 to avoid sleeping delays during test
    ws = await websocket_client.connect_ws("ws://host/ws/sync?token=t", max_retries=2, backoff_base=0)
    assert ws is dummy


@pytest.mark.asyncio
async def test_reader_calls_on_error_for_unexpected_exception():
    ws = DummyWSShort()

    called = {"err": None}

    async def on_message(_):
        pytest.fail("on_message should not be called")

    async def on_error(e: Exception):
        called["err"] = e

    stop_event = asyncio.Event()

    await websocket_client.reader_loop(ws, on_message, on_error, stop_event)

    assert isinstance(called["err"], Exception)
    assert str(called["err"]) == "boom"


@pytest.mark.asyncio
async def test_sender_loop_stops_and_sends_queue_items():
    sent = []

    class WS:
        async def send(self, payload: str):
            sent.append(payload)

    ws = WS()
    q = asyncio.Queue()
    stop_event = asyncio.Event()

    await q.put(websocket_client.make_ws_message("event_update", {"a": 1}))

    task = asyncio.create_task(websocket_client.sender_loop(ws, q, stop_event))
    # give the sender a short moment to process
    await asyncio.sleep(0.02)
    stop_event.set()
    await asyncio.wait_for(task, timeout=1.0)

    assert sent, "No messages were sent by sender_loop"
    parsed = json.loads(sent[0])
    assert parsed["type"] == "event_update"
    assert parsed["payload"]["a"] == 1


def test_render_websocket_client_shows_url_when_logged_in(monkeypatch):
    # Ensure auth_utils.is_logged_in returns True
    monkeypatch.setattr(auth_utils, "is_logged_in", lambda: True)

    # Create a minimal fake Streamlit shim that render_websocket_client expects
    class FakeStreamlit:
        def __init__(self):
            self.session_state = {}
        def warning(self, *a, **k):
            return None
        def write(self, *a, **k):
            return None
        def text_input(self, label, value=None, key=None, disabled=False):
            # emulate text_input writing into session_state like Streamlit shim
            if key:
                self.session_state[key] = value
            return value
        def text_area(self, *a, **k):
            return k.get('value', '{}')
        def button(self, *a, **k):
            return False
        def subheader(self, *a, **k):
            return None
        def json(self, *a, **k):
            return None
        def error(self, *a, **k):
            return None

    fake_st = FakeStreamlit()
    fake_st.session_state["access_token"] = "tok123"

    # monkeypatch auth_utils.st to our fake
    monkeypatch.setattr(auth_utils, "st", fake_st)

    # call render; it should populate ws_url key in session_state via text_input
    websocket_client.render_websocket_client()

    assert "ws_url" in fake_st.session_state
    assert "token=tok123" in fake_st.session_state.get("ws_url", "")
