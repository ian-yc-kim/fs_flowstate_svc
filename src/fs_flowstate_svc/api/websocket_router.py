import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends

from fs_flowstate_svc.schemas.websocket_schemas import WebSocketMessage
from fs_flowstate_svc.auth import jwt_handler
from fs_flowstate_svc.services import user_service
from fs_flowstate_svc.models.base import get_db
from fs_flowstate_svc.config import settings

logger = logging.getLogger("fs_flowstate_svc.api.websocket_router")

websocket_router = APIRouter()


class ConnectionManager:
    """Manage active websocket connections per user and track last pong timestamps.

    Improvements:
    - Track per-WebSocket event loop when connections are added.
    - Maintain a reverse mapping from ws id to owning user_id to avoid scanning all users
      when cleaning up a failed connection (performance improvement).
    - When broadcasting from sync contexts, schedule per-connection run_coroutine_threadsafe
      onto the specific loop that services that WebSocket. This avoids relying on a single
      stored server loop which may become stale/closed across test lifecycles.
    """

    def __init__(self) -> None:
        # registry: user_id (str) -> list of WebSocket objects
        self.registry: Dict[str, List[WebSocket]] = defaultdict(list)
        # last_pong: user_id -> (ws_id -> datetime)
        self.last_pong: Dict[str, Dict[int, datetime]] = defaultdict(dict)
        # per-ws loop mapping: user_id -> (ws_id -> loop)
        self._ws_loops: Dict[str, Dict[int, asyncio.AbstractEventLoop]] = defaultdict(dict)
        # reverse mapping: ws_id -> user_id for fast lookup
        self._ws_to_user: Dict[int, str] = {}
        # optional stored server loop (legacy fallback)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def add(self, user_id: str, ws: WebSocket) -> None:
        try:
            self.registry[user_id].append(ws)
            self.last_pong[user_id][id(ws)] = datetime.utcnow()
            self._ws_to_user[id(ws)] = user_id
            # capture the running loop for this websocket connection if available
            try:
                loop = asyncio.get_running_loop()
                self._ws_loops[user_id][id(ws)] = loop
                # also ensure a module-level server loop is known for fallback
                if self._loop is None:
                    self._loop = loop
            except RuntimeError:
                # not running in an event loop here; that's fine
                pass
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
            # remove per-ws loop tracking if present
            if id(ws) in self._ws_loops.get(user_id, {}):
                self._ws_loops[user_id].pop(id(ws), None)
            # remove reverse mapping
            self._ws_to_user.pop(id(ws), None)
            if not conns:
                self.registry.pop(user_id, None)
                self.last_pong.pop(user_id, None)
                self._ws_loops.pop(user_id, None)
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

    async def _send_single(self, ws: WebSocket, message: WebSocketMessage) -> None:
        """Send a single message to a websocket. If it fails, remove the connection."""
        try:
            # Ensure payload is JSON-serializable. Use Pydantic json-mode dump when available.
            if hasattr(message, "model_dump"):
                try:
                    payload = message.model_dump(mode="json")
                except TypeError:
                    # Older pydantic versions or unexpected signature: fallback
                    payload = message.model_dump()
            else:
                payload = message
            await ws.send_json(payload)
        except Exception:
            logger.error("Error sending websocket message to single connection, removing", exc_info=True)
            # Best-effort remove; use reverse mapping to avoid scanning all users
            try:
                uid = self._ws_to_user.get(id(ws))
                if uid:
                    try:
                        self.remove(uid, ws)
                    except Exception:
                        logger.error("Failed removing dead websocket via reverse mapping", exc_info=True)
                else:
                    # Fallback: attempt a limited scan (very rare) but avoid full expensive operations
                    for uid_scan, conns in list(self.registry.items()):
                        if ws in conns:
                            try:
                                self.remove(uid_scan, ws)
                            except Exception:
                                logger.error("Failed removing dead websocket during fallback scan", exc_info=True)
                            break
            except Exception:
                logger.error("Failed cleanup after send_single failure", exc_info=True)

    async def _broadcast(self, user_id: str, message: WebSocketMessage) -> None:
        """Internal async broadcast: send message to all active websockets for user."""
        conns = list(self.registry.get(user_id, []))
        for ws in conns:
            try:
                await self._send_single(ws, message)
            except Exception:
                # _send_single already logs and removes; continue
                pass

    def broadcast_to_user(self, user_id: str, message: WebSocketMessage) -> None:
        """Schedule broadcasting to a user's active websockets.

        Strategy:
        - Prefer scheduling run_coroutine_threadsafe on each connection's captured loop.
        - If a connection has no loop or its loop is closed, skip that connection.
        - If no per-connection loops available, fall back to scheduling the whole broadcast
          on a stored server loop (if present and running).
        - As a last resort, try to schedule on current running loop if caller is in an event loop.
        - Any failure to schedule will be logged but will not raise.
        """
        try:
            conns = list(self.registry.get(user_id, []))
            if not conns:
                logger.debug("No active connections for user %s; nothing to broadcast", user_id)
                return

            scheduled = False
            # Try per-connection loops first
            for ws in conns:
                loop = self._ws_loops.get(user_id, {}).get(id(ws))
                if loop is not None:
                    try:
                        if not loop.is_closed():
                            fut = asyncio.run_coroutine_threadsafe(self._send_single(ws, message), loop)

                            def _cb(f):
                                try:
                                    f.result()
                                except Exception:
                                    logger.error("Per-connection broadcast task failed", exc_info=True)

                            fut.add_done_callback(_cb)
                            scheduled = True
                            continue
                        else:
                            # drop mapping for closed loop
                            logger.debug("Per-connection loop closed for user %s, ws %s", user_id, id(ws))
                            self._ws_loops[user_id].pop(id(ws), None)
                    except Exception:
                        logger.warning("Per-connection scheduling failed, will try other mechanisms", exc_info=True)
                        # fallthrough to other scheduling attempts

            if scheduled:
                return

            # If no per-connection scheduling succeeded, try stored server loop
            if self._loop is not None:
                try:
                    if not self._loop.is_closed():
                        fut = asyncio.run_coroutine_threadsafe(self._broadcast(user_id, message), self._loop)

                        def _cb_all(f):
                            try:
                                f.result()
                            except Exception:
                                logger.error("Broadcast task on stored loop failed", exc_info=True)

                        fut.add_done_callback(_cb_all)
                        return
                    else:
                        logger.warning("Stored event loop is closed, clearing reference")
                        self._loop = None
                except Exception:
                    logger.warning("Stored event loop scheduling failed, clearing reference", exc_info=True)
                    self._loop = None

            # If caller is in an event loop, schedule directly
            try:
                running = asyncio.get_running_loop()
                running.create_task(self._broadcast(user_id, message))
                return
            except RuntimeError:
                # not in an event loop
                pass

            logger.warning("No available event loop; dropping broadcast for user %s", user_id)
        except Exception as e:
            logger.error(e, exc_info=True)


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

        # ensure manager has server loop reference
        try:
            if connection_manager._loop is None:
                # Use running loop at the time of accepting connection
                connection_manager._loop = asyncio.get_running_loop()
        except Exception:
            # if get_running_loop fails, continue without loop
            logger.error("Failed to set connection manager event loop", exc_info=True)

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
