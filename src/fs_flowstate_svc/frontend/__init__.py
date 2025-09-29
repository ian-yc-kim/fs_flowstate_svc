from . import auth_utils
from . import websocket_client

# Optional import for inbox drag helpers. Keep import guarded to avoid
# breaking import-time behavior in test environments where dependencies
# like streamlit may be shimed or unavailable.
try:
    from . import inbox_drag  # type: ignore
except Exception:
    inbox_drag = None

# Expose keyboard utilities at package level. If import fails or the
# module is missing expected symbols (e.g. in constrained test
# environments), provide a lightweight shim object implementing the
# minimal API used by frontend tests to avoid import-time breakage.
import logging
logger = logging.getLogger(__name__)

try:
    from . import keyboard_utils  # type: ignore
    # Validate expected attributes exist
    if not hasattr(keyboard_utils, "ensure_keyboard_listener") or not hasattr(keyboard_utils, "read_and_clear_last_key"):
        raise ImportError("keyboard_utils missing expected attributes")
except Exception as e:
    logger.debug("keyboard_utils import failed or incomplete, using shim", exc_info=True)

    class _KeyboardShim:
        """Minimal shim exposing the helpers tests expect.

        This mirrors the semantics of the real helpers but avoids importing
        optional frontend dependencies at package import time.
        """

        def ensure_keyboard_listener(self, st, key_prefix: str = "inbox") -> None:
            try:
                st.session_state.setdefault(f"{key_prefix}_last_key", None)
                st.session_state.setdefault(f"{key_prefix}_last_key_shift", False)
            except Exception:
                logger.error("shim.ensure_keyboard_listener failed", exc_info=True)

        def read_and_clear_last_key(self, st, key_prefix: str = "inbox"):
            try:
                key = st.session_state.get(f"{key_prefix}_last_key")
                shift = bool(st.session_state.get(f"{key_prefix}_last_key_shift", False))
                try:
                    st.session_state[f"{key_prefix}_last_key"] = None
                    st.session_state[f"{key_prefix}_last_key_shift"] = False
                except Exception:
                    try:
                        st.session_state.pop(f"{key_prefix}_last_key", None)
                        st.session_state.pop(f"{key_prefix}_last_key_shift", None)
                    except Exception:
                        pass
                return (key, shift)
            except Exception:
                logger.error("shim.read_and_clear_last_key failed", exc_info=True)
                return (None, False)

    keyboard_utils = _KeyboardShim()

__all__ = ["auth_utils", "websocket_client", "inbox_drag", "keyboard_utils"]
