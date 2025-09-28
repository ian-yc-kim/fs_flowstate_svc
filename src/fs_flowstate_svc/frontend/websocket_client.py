import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from fs_flowstate_svc.frontend import auth_utils
from fs_flowstate_svc.schemas.websocket_schemas import WebSocketMessage
from fs_flowstate_svc.config import settings

# lazy import websockets so tests can mock the module
try:
    import websockets  # type: ignore
except Exception:  # pragma: no cover - import errors surfaced in environment without package
    websockets = None

logger = logging.getLogger(__name__)

# Type aliases
OnMessageType = Callable[[Dict[str, Any]], Awaitable[None]]
OnErrorType = Callable[[Exception], Awaitable[None]]


def build_ws_url(token: str, host: str = "localhost", port: int = 8000) -> str:
    """Construct websocket URL with JWT token as query param."""
    return f"ws://{host}:{port}/ws/sync?token={token}"


def make_ws_message(msg_type: str, payload: Optional[Dict[str, Any]] = None) -> str:
    payload = payload or {}
    msg = WebSocketMessage(type=msg_type, payload=payload)
    # use pydantic v2 model_dump_json per project rules
    return msg.model_dump_json()


async def connect_ws(url: str, max_retries: int = 3, backoff_base: float = 0.1):
    """Attempt to open a websocket connection with retries.

    Returns the connected websocket client protocol.
    """
    if websockets is None:
        raise RuntimeError("websockets package not available")

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            ws = await websockets.connect(url)
            logger.info("WebSocket connected to %s", url)
            return ws
        except Exception as e:
            last_exc = e
            logger.error(e, exc_info=True)
            # exponential backoff-ish
            await asyncio.sleep(backoff_base * attempt)
    # all retries failed
    logger.error("Failed to connect websocket after %d attempts", max_retries)
    raise last_exc


async def sender_loop(ws, outgoing: "asyncio.Queue[str]", stop_event: asyncio.Event):
    """Send JSON messages from outgoing queue until stop_event is set."""
    try:
        while not stop_event.is_set():
            try:
                msg = await asyncio.wait_for(outgoing.get(), timeout=0.1)
            except asyncio.TimeoutError:
                await asyncio.sleep(0)  # yield control
                continue

            try:
                await ws.send(msg)
            except Exception as e:
                logger.error(e, exc_info=True)
                break
    except asyncio.CancelledError:
        logger.debug("sender_loop cancelled")
    except Exception as e:
        logger.error(e, exc_info=True)


async def reader_loop(ws, on_message: OnMessageType, on_error: OnErrorType, stop_event: asyncio.Event):
    """Read incoming messages and dispatch. Respond to ping frames with pong."""
    try:
        while not stop_event.is_set():
            try:
                raw = await ws.recv()
            except Exception as e:
                # recv failures indicate closed connection or other errors
                msg = str(e).lower()
                logger.error(e, exc_info=True)
                # Treat expected clean closure as normal termination (do not call on_error)
                # Tests and some websocket clients may raise a generic Exception('closed')
                if "closed" in msg or "connection closed" in msg or "connectionclosed" in msg:
                    break
                # For other unexpected errors, notify error handler
                try:
                    await on_error(e)
                except Exception:
                    logger.error("on_error callback failed", exc_info=True)
                break

            try:
                if isinstance(raw, (bytes, bytearray)):
                    raw_text = raw.decode()
                else:
                    raw_text = str(raw)

                data = json.loads(raw_text)
                # validate basic shape via pydantic model
                try:
                    parsed = WebSocketMessage.model_validate(data)
                except Exception as e:
                    logger.error("Invalid message format", exc_info=True)
                    # send back an error frame if possible
                    try:
                        err = WebSocketMessage(type="error", payload={"detail": "invalid_message"})
                        await ws.send(err.model_dump_json())
                    except Exception:
                        logger.error("Failed to send invalid_message response", exc_info=True)
                    continue

                # heartbeat: respond to ping
                if parsed.type == "ping":
                    try:
                        pong = WebSocketMessage(type="pong", payload={})
                        await ws.send(pong.model_dump_json())
                    except Exception as e:
                        logger.error("Failed sending pong", exc_info=True)
                    continue

                # update pong handled server-side; deliver other messages
                await on_message(parsed.model_dump())

            except json.JSONDecodeError as e:
                logger.error(e, exc_info=True)
                # try to notify server
                try:
                    err = WebSocketMessage(type="error", payload={"detail": "invalid_json"})
                    await ws.send(err.model_dump_json())
                except Exception:
                    logger.error("Failed sending invalid_json response", exc_info=True)
            except Exception as e:
                logger.error(e, exc_info=True)
                try:
                    await on_error(e)
                except Exception:
                    logger.error("on_error callback failed", exc_info=True)
                break
    except asyncio.CancelledError:
        logger.debug("reader_loop cancelled")
    except Exception as e:
        logger.error(e, exc_info=True)


# Streamlit integration function
def render_websocket_client() -> None:
    """Render a simple Streamlit UI for websocket interaction.

    This function is intentionally simple so core async logic can be unit tested separately.
    """
    st = auth_utils.st

    # session state keys
    st.session_state.setdefault("ws_status", "disconnected")
    st.session_state.setdefault("ws_messages", [])
    st.session_state.setdefault("ws_error", "")

    token = st.session_state.get("access_token") if auth_utils.is_logged_in() else None

    host = "localhost"
    port = getattr(settings, "SERVICE_PORT", 8000)

    st.write("WebSocket Client")

    if not token:
        st.warning("Not logged in. Connect disabled.")
        return

    url = build_ws_url(token, host=host, port=port)
    st.text_input("WebSocket URL", value=url, key="ws_url", disabled=True)

    # simple connect/disconnect actions
    if st.button("Connect"):
        st.session_state["ws_status"] = "connecting"
        # create background task to manage connection
        # For Streamlit environment we run a detached asyncio task
        loop = asyncio.get_event_loop()
        if "_ws_task" not in st.session_state:
            st.session_state["_ws_task"] = loop.create_task(_bg_ws_manager(url))

    if st.button("Disconnect"):
        st.session_state["ws_status"] = "disconnecting"
        # signal background task to stop
        if "_ws_stop_event" in st.session_state:
            st.session_state["_ws_stop_event"].set()

    st.write(f"Status: {st.session_state.get('ws_status')} ")
    if st.session_state.get("ws_error"):
        st.error(st.session_state.get("ws_error"))

    # message send area
    msg_type = st.text_input("Message type", value="event_update", key="_msg_type")
    payload_text = st.text_area("Payload (JSON)", value="{}", key="_msg_payload")
    if st.button("Send"):
        try:
            payload = json.loads(payload_text)
            msg_json = make_ws_message(msg_type, payload)
            # push into outgoing queue if present
            q = st.session_state.get("_ws_outgoing")
            if q:
                q.put_nowait(msg_json)
            else:
                st.error("Not connected to websocket")
        except Exception as e:
            logger.error(e, exc_info=True)
            st.error("Invalid payload JSON")

    # show messages
    st.subheader("Received Messages")
    for m in reversed(st.session_state.get("ws_messages", [])):
        st.json(m)


async def _bg_ws_manager(url: str) -> None:
    """Background manager used by Streamlit integration.

    Keeps a reader and sender loop, updates session_state accordingly.
    """
    st = auth_utils.st
    stop_event = asyncio.Event()
    outgoing: asyncio.Queue[str] = asyncio.Queue()
    st.session_state["_ws_stop_event"] = stop_event
    st.session_state["_ws_outgoing"] = outgoing

    try:
        st.session_state["ws_status"] = "connecting"
        ws = await connect_ws(url, max_retries=3, backoff_base=1)
        st.session_state["ws_status"] = "connected"

        async def _on_message(data: Dict[str, Any]):
            try:
                st.session_state.setdefault("ws_messages", []).append(data)
            except Exception:
                logger.error("Failed updating session messages", exc_info=True)

        async def _on_error(e: Exception):
            st.session_state["ws_error"] = str(e)
            st.session_state["ws_status"] = "error"

        reader = asyncio.create_task(reader_loop(ws, _on_message, _on_error, stop_event))
        sender = asyncio.create_task(sender_loop(ws, outgoing, stop_event))

        # wait until stop_event triggered
        await stop_event.wait()

    except Exception as e:
        logger.error(e, exc_info=True)
        st.session_state["ws_error"] = str(e)
        st.session_state["ws_status"] = "error"
    finally:
        try:
            stop_event.set()
            # cancel tasks if exist
            for tname in ("reader", "sender"):
                t = locals().get(tname)
                if isinstance(t, asyncio.Task):
                    t.cancel()
                    try:
                        await t
                    except Exception:
                        pass
            try:
                await ws.close()
            except Exception:
                pass
        except Exception:
            logger.error("Error during ws manager cleanup", exc_info=True)
        finally:
            st.session_state["ws_status"] = "disconnected"
