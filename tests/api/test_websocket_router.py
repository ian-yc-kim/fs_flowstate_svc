import json
import pytest
import time
from fs_flowstate_svc.auth import jwt_handler
from fs_flowstate_svc.services import user_service
from fs_flowstate_svc.schemas.user_schemas import UserCreate
from fs_flowstate_svc.api.websocket_router import connection_manager
from fs_flowstate_svc.config import settings
from fs_flowstate_svc.schemas.websocket_schemas import WebSocketMessage


class TestWebSocketRouter:
    def test_connect_success_with_valid_jwt(self, client, db_session, monkeypatch):
        # ensure secrets available (defaults exist but keep explicit)
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)

        # create a user
        user = user_service.create_user(db_session, UserCreate(username="wsuser", email="ws@example.com", password="pass1234"))
        token = jwt_handler.create_access_token({"sub": str(user.id)})

        # no active connections initially
        assert connection_manager.total() == 0

        with client.websocket_connect(f"/ws/sync?token={token}") as ws:
            # after connect, registry should reflect connection
            assert connection_manager.total() >= 1

            # send an event_update and expect ack
            ws.send_json({"type": "event_update", "payload": {"x": 1}})
            msg = ws.receive_json()
            assert msg["type"] == "ack"
            assert msg["payload"]["received_type"] == "event_update"

        # after context exit, connection removed
        # slight wait for cleanup task
        time.sleep(0.05)
        assert connection_manager.total() == 0

    def test_reject_missing_or_invalid_jwt(self, client, db_session, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)

        # missing token
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/sync"):
                pass

        # invalid token
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/sync?token=invalid.token"):
                pass

    def test_message_format_enforced(self, client, db_session, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)

        user = user_service.create_user(db_session, UserCreate(username="fmtuser", email="fmt@example.com", password="pwd12345"))
        token = jwt_handler.create_access_token({"sub": str(user.id)})

        with client.websocket_connect(f"/ws/sync?token={token}") as ws:
            # send invalid json as text
            ws.send_text("not-json")
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["payload"]["detail"] == "invalid_message"

    def test_ping_pong_heartbeat_and_routing(self, client, db_session, monkeypatch):
        # speed up heartbeat for test stability
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        # set small intervals
        monkeypatch.setattr(settings, "WS_PING_INTERVAL_SECONDS", 0.1)
        monkeypatch.setattr(settings, "WS_PONG_TIMEOUT_SECONDS", 1)

        user = user_service.create_user(db_session, UserCreate(username="hbuser", email="hb@example.com", password="pwd12345"))
        token = jwt_handler.create_access_token({"sub": str(user.id)})

        with client.websocket_connect(f"/ws/sync?token={token}") as ws:
            # expect a ping from server
            msg = ws.receive_json()
            assert msg["type"] == "ping"

            # respond with pong and then send an event
            ws.send_json({"type": "pong", "payload": {}})

            ws.send_json({"type": "inbox_update", "payload": {"item": 1}})
            ack = ws.receive_json()
            assert ack["type"] == "ack"

            # client-initiated ping should receive pong
            ws.send_json({"type": "ping", "payload": {}})
            resp = ws.receive_json()
            assert resp["type"] == "pong"

    def test_connection_registry_add_remove(self, client, db_session, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)

        user = user_service.create_user(db_session, UserCreate(username="reguser", email="reg@example.com", password="pwd12345"))
        token = jwt_handler.create_access_token({"sub": str(user.id)})

        before = connection_manager.total()
        with client.websocket_connect(f"/ws/sync?token={token}") as ws:
            assert connection_manager.total() == before + 1
        # allow cleanup
        time.sleep(0.05)
        assert connection_manager.total() == before

    def test_broadcast_to_user_fanout(self, client, db_session, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)

        user = user_service.create_user(db_session, UserCreate(username="fanout", email="fanout@example.com", password="pwd12345"))
        token = jwt_handler.create_access_token({"sub": str(user.id)})

        # open two websocket connections
        with client.websocket_connect(f"/ws/sync?token={token}") as ws1:
            with client.websocket_connect(f"/ws/sync?token={token}") as ws2:
                # drain initial messages (likely pings)
                for _ in range(2):
                    m1 = ws1.receive_json()
                    m2 = ws2.receive_json()
                # send broadcast from server side
                msg = WebSocketMessage(type="event_created", payload={"x": 1})
                connection_manager.broadcast_to_user(str(user.id), msg)
                # both should receive
                r1 = ws1.receive_json()
                r2 = ws2.receive_json()
                assert r1["type"] == "event_created"
                assert r2["type"] == "event_created"
