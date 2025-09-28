import pytest
import time
from fs_flowstate_svc.auth import jwt_handler
from fs_flowstate_svc.services import user_service
from fs_flowstate_svc.schemas.user_schemas import UserCreate
from fs_flowstate_svc.schemas.websocket_schemas import WebSocketMessage


def register_user(client, username: str, email: str, password: str):
    r = client.post("/users/register", json={"username": username, "email": email, "password": password})
    assert r.status_code == 200
    return r.json()


def login(client, username_or_email: str, password: str):
    r = client.post("/users/login", json={"username_or_email": username_or_email, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def get_auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def _drain_until_expected(ws, expected_prefixes, attempts=10):
    for _ in range(attempts):
        msg = ws.receive_json()
        t = msg.get("type", "")
        if any(t.startswith(p) for p in expected_prefixes):
            return msg
    return None


class TestEventRealtime:
    def test_event_create_update_delete_broadcasts(self, client, db_session, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)

        user = register_user(client, "re_user", "re@example.com", "password")
        token = login(client, "re_user", "password")
        headers = get_auth_headers(token)

        with client.websocket_connect(f"/ws/sync?token={token}") as ws:
            # drain initial ping
            initial = ws.receive_json()
            assert initial["type"] == "ping"

            # create event
            payload = {
                "title": "RT Meeting",
                "description": "Real time",
                "start_time": "2024-01-20T10:00:00Z",
                "end_time": "2024-01-20T11:00:00Z"
            }
            r = client.post("/api/events/", json=payload, headers=headers)
            assert r.status_code == 201
            created = r.json()

            # wait for event_created
            msg = _drain_until_expected(ws, ["event_created", "event_updated", "event_deleted"], attempts=5)
            assert msg is not None and msg["type"] == "event_created"
            assert msg["payload"]["id"] == created["id"]

            # update event
            up = {"title": "RT Meeting Updated", "start_time": "2024-01-20T12:00:00Z", "end_time": "2024-01-20T13:00:00Z"}
            r2 = client.put(f"/api/events/{created['id']}", json=up, headers=headers)
            assert r2.status_code == 200
            updated = r2.json()

            msg2 = _drain_until_expected(ws, ["event_created", "event_updated", "event_deleted"], attempts=5)
            assert msg2 is not None and msg2["type"] == "event_updated"
            assert msg2["payload"]["id"] == updated["id"]

            # delete event
            r3 = client.delete(f"/api/events/{created['id']}", headers=headers)
            assert r3.status_code == 204

            msg3 = _drain_until_expected(ws, ["event_deleted"], attempts=5)
            assert msg3 is not None and msg3["type"] == "event_deleted"
            assert msg3["payload"]["event_id"] == created["id"]
