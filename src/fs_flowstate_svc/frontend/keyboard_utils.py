import logging
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


def ensure_keyboard_listener(st: Any, key_prefix: str = "inbox") -> None:
    """Ensure keyboard session keys exist.

    This function is intentionally lightweight so it works in test shims
    (FakeStreamlit). In real Streamlit deployments JS may be injected here
    to capture Tab/Enter/Escape and set the session_state keys. Tests can
    bypass JS by directly setting session_state keys.
    """
    try:
        st.session_state.setdefault(f"{key_prefix}_last_key", None)
        st.session_state.setdefault(f"{key_prefix}_last_key_shift", False)
        st.session_state.setdefault(f"{key_prefix}_focus_target", None)
        st.session_state.setdefault(f"{key_prefix}_focus_index", 0)
        st.session_state.setdefault(f"{key_prefix}_focus_registry", [])
    except Exception as e:
        logger.error(e, exc_info=True)


def read_and_clear_last_key(st: Any, key_prefix: str = "inbox") -> Tuple[Optional[str], bool]:
    """Read last key and shift flag then clear them. Returns (key, shift).

    This is best-effort: clearing may use assignment or pop depending on
    the session_state implementation in tests/shims.
    """
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
                # give up silently
                pass
        return (key, shift)
    except Exception as e:
        logger.error(e, exc_info=True)
        return (None, False)


def set_focus_target(st: Any, key_prefix: str, target_id: Optional[str]) -> None:
    """Persist a focus target identifier in session state.

    The UI rendering layer can emit HTML with matching data-focus-id attributes
    so JS (or manual test assertions) can ensure the right element receives
    focus.
    """
    try:
        st.session_state[f"{key_prefix}_focus_target"] = target_id
    except Exception as e:
        logger.error(e, exc_info=True)


def get_focus_target(st: Any, key_prefix: str) -> Optional[str]:
    """Return the persisted focus target id, if any."""
    try:
        return st.session_state.get(f"{key_prefix}_focus_target")
    except Exception as e:
        logger.error(e, exc_info=True)
        return None


def cycle_focus(index: int, total: int, shift: bool = False) -> int:
    """Compute the next focus index with wrap-around.

    If total is 0 return 0. shift=True means move backward (Shift+Tab).
    """
    try:
        if total <= 0:
            return 0
        if shift:
            # move backward with wrap
            return (index - 1) % total
        return (index + 1) % total
    except Exception as e:
        logger.error(e, exc_info=True)
        return 0


def clear_focus_target(st: Any, key_prefix: str) -> None:
    """Clear any stored focus target."""
    try:
        st.session_state[f"{key_prefix}_focus_target"] = None
    except Exception as e:
        logger.error(e, exc_info=True)
