import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends

from fs_flowstate_svc.schemas.websocket_schemas import WebSocketMessage
from fs_flowstate_svc.auth import jwt_handler
from fs_flowstate_svc.services import user_service
from fs_flowstate_svc.models.base import get_db
from fs_flowstate_svc.config import settings

logger = logging.getLogger("fs_flowstate_svc.api.websocket_router")

websocket_router = APIRouter()


class ConnectionManager:
    """Manage active websocket connections per user and track last pong timestamps."""

    def __init__(self) -> None:
        # registry: user_id (str) -> list of WebSocket objects
        self.registry: Dict[str, List[WebSocket]] = defaultdict(list)
        # last_pong: (user_id, ws_id) -> datetime
        self.last_pong: Dict[str, Dict[int, datetime]] = defaultdict(dict)

    def add(self, user_id: str, ws: WebSocket) -> None:
        try:
            self.registry[user_id].append(ws)
            self.last_pong[user_id][id(ws)] = datetime.utcnow()
            logger.info("Added websocket for user %s. Connections: %d", user_id, len(self.registry[user_id]))
        except Exception as e:
            logger.error(e, exc_info=True)
            raise

    def remove(self, user_id: str, ws: WebSocket) -> None:
        try:
            conns = self.registry.get(user_id, [])
            if ws in conns:
                conns.remove(ws)
            self.last_pong[user_id].pop(id(ws), None)
            if not conns:
                self.registry.pop(user_id, None)
                self.last_pong.pop(user_id, None)
            logger.info("Removed websocket for user %s. Remaining: %d", user_id, len(self.registry.get(user_id, [])))
        except Exception as e:
            logger.error(e, exc_info=True)
            raise

    def get_user_connections(self, user_id: str):
        return list(self.registry.get(user_id, []))

    def total(self) -> int:
        return sum(len(v) for v in self.registry.values())

    def user_count(self, user_id: str) -> int:
        return len(self.registry.get(user_id, []))

    def update_pong(self, user_id: str, ws: WebSocket) -> None:
        try:
            self.last_pong[user_id][id(ws)] = datetime.utcnow()
        except Exception:
            logger.error("Failed updating pong timestamp", exc_info=True)

    def last_pong_for(self, user_id: str, ws: WebSocket) -> datetime:
        return self.last_pong.get(user_id, {}).get(id(ws), datetime.utcfromtimestamp(0))


# module-level manager used by app and tests
connection_manager = ConnectionManager()


async def _ping_loop(websocket: WebSocket, user_id: str, stop_event: asyncio.Event) -> None:
    """Sends ping messages periodically and closes connection if pong not received in time."""
    ping_interval = getattr(settings, "WS_PING_INTERVAL_SECONDS", 15)
    pong_timeout = getattr(settings, "WS_PONG_TIMEOUT_SECONDS", 45)

    try:
        while not stop_event.is_set():
            await asyncio.sleep(ping_interval)
            try:
                msg = WebSocketMessage(type="ping", payload={})
                await websocket.send_json(msg.model_dump())
                logger.debug("Sent ping to user %s", user_id)
            except Exception as e:
                logger.error("Error sending ping", exc_info=True)
                # If sending fails, exit loop and let outer handler cleanup
                break

            # check last_pong
            last = connection_manager.last_pong_for(user_id, websocket)
            if (datetime.utcnow() - last).total_seconds() > pong_timeout:
                logger.warning("Pong timeout for user %s, closing websocket", user_id)
                try:
                    await websocket.close(code=4000)
                except Exception:
                    logger.error("Error closing websocket after pong timeout", exc_info=True)
                break
    except asyncio.CancelledError:
        logger.debug("Ping loop cancelled for user %s", user_id)
    except Exception as e:
        logger.error(e, exc_info=True)


@websocket_router.websocket("/sync")
async def websocket_sync(websocket: WebSocket, token: str = Query(None), db=Depends(get_db)):
    """WebSocket endpoint supporting JWT auth, connection registry, standardized messages, and heartbeat."""
    user = None
    ping_task = None
    stop_event = asyncio.Event()

    # Authentication before accepting
    try:
        if not token:
            logger.warning("WebSocket connection attempt without token")
            # reject by closing with policy violation / unauthorized code
            await websocket.close(code=1008)
            return

        # validate token
        try:
            jwt_handler.decode_token(token)
        except Exception as e:
            logger.warning("Invalid token on websocket connect", exc_info=True)
            await websocket.close(code=1008)
            return

        # get user via user service
        try:
            user = user_service.get_current_user(db, token)
        except Exception as e:
            logger.warning("Failed to fetch user on websocket connect", exc_info=True)
            await websocket.close(code=1008)
            return

        # Accept connection
        await websocket.accept()
        connection_manager.add(str(user.id), websocket)

        # Start ping loop
        ping_task = asyncio.create_task(_ping_loop(websocket, str(user.id), stop_event))

        # Receive loop
        while True:
            try:
                text = await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected for user %s", user.id)
                break
            except Exception as e:
                logger.error("Error receiving websocket message", exc_info=True)
                break

            # parse and validate message
            try:
                data = json.loads(text)
                msg = WebSocketMessage.model_validate(data)
            except Exception as e:
                logger.error("Invalid message format", exc_info=True)
                try:
                    err = WebSocketMessage(type="error", payload={"detail": "invalid_message"})
                    await websocket.send_json(err.model_dump())
                except Exception:
                    logger.error("Failed sending error message", exc_info=True)
                continue

            # routing based on type
            try:
                if msg.type == "ping":
                    # client requested ping -> respond pong
                    resp = WebSocketMessage(type="pong", payload={})
                    await websocket.send_json(resp.model_dump())
                elif msg.type == "pong":
                    # update last pong
                    connection_manager.update_pong(str(user.id), websocket)
                elif msg.type in ("event_update", "inbox_update"):
                    logger.info("Received %s from user %s: %s", msg.type, user.id, msg.payload)
                    ack = WebSocketMessage(type="ack", payload={"received_type": msg.type, "status": "ok"})
                    await websocket.send_json(ack.model_dump())
                else:
                    logger.info("Unknown message type %s from user %s", msg.type, user.id)
                    unk = WebSocketMessage(type="error", payload={"detail": "unknown_type"})
                    await websocket.send_json(unk.model_dump())
            except Exception as e:
                logger.error("Error routing message", exc_info=True)
                try:
                    err = WebSocketMessage(type="error", payload={"detail": "internal_error"})
                    await websocket.send_json(err.model_dump())
                except Exception:
                    logger.error("Failed sending internal error message", exc_info=True)

    except Exception as e:
        logger.error("Unexpected websocket error", exc_info=True)
    finally:
        # cleanup
        try:
            stop_event.set()
            if ping_task:
                ping_task.cancel()
                try:
                    await ping_task
                except Exception:
                    pass
            if user is not None:
                try:
                    connection_manager.remove(str(user.id), websocket)
                except Exception:
                    logger.error("Error removing websocket from registry", exc_info=True)
            try:
                await websocket.close()
            except Exception:
                # websocket may already be closed
                pass
        except Exception:
            logger.error("Error during websocket cleanup", exc_info=True)
