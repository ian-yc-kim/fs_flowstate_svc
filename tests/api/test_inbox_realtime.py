import pytest
import time
from fs_flowstate_svc.auth import jwt_handler
from fs_flowstate_svc.services import user_service
from fs_flowstate_svc.schemas.user_schemas import UserCreate


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


class TestInboxRealtime:
    def test_inbox_create_update_delete_broadcasts(self, client, db_session, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)

        user = register_user(client, "in_user", "in@example.com", "password")
        token = login(client, "in_user", "password")
        headers = get_auth_headers(token)

        with client.websocket_connect(f"/ws/sync?token={token}") as ws:
            # drain initial ping
            initial = ws.receive_json()
            assert initial["type"] == "ping"

            # create inbox item
            payload = {"content": "RT Inbox", "category": "TODO", "priority": 3, "status": "PENDING"}
            r = client.post("/api/inbox/", json=payload, headers=headers)
            assert r.status_code == 201
            created = r.json()

            # wait for inbox_item_created
            msg = _drain_until_expected(ws, ["inbox_item_created", "inbox_item_updated", "inbox_item_deleted"], attempts=5)
            assert msg is not None and msg["type"] == "inbox_item_created"
            assert msg["payload"]["id"] == created["id"]

            # update inbox item
            up = {"content": "RT Inbox Updated", "status": "DONE"}
            r2 = client.put(f"/api/inbox/{created['id']}", json=up, headers=headers)
            assert r2.status_code == 200
            updated = r2.json()

            msg2 = _drain_until_expected(ws, ["inbox_item_updated"], attempts=5)
            assert msg2 is not None and msg2["type"] == "inbox_item_updated"
            assert msg2["payload"]["id"] == updated["id"]

            # delete inbox item
            r3 = client.delete(f"/api/inbox/{created['id']}", headers=headers)
            assert r3.status_code == 204

            msg3 = _drain_until_expected(ws, ["inbox_item_deleted"], attempts=5)
            assert msg3 is not None and msg3["type"] == "inbox_item_deleted"
            assert msg3["payload"]["inbox_item_id"] == created["id"]
