import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _load_impl() -> Optional[Any]:
    """Lazy-load the real implementation to avoid import-time failures in tests.

    Returns the implementation module or None when it cannot be imported.
    """
    try:
        # import inside function to defer possible heavy imports and side-effects
        from .pages import inbox_drag as _impl  # type: ignore
        return _impl
    except Exception:
        logger.debug("Could not import frontend.pages.inbox_drag", exc_info=True)
        return None


def _call_or_default(fn_name: str, *args, default: Any = None, **kwargs) -> Any:
    impl = _load_impl()
    if impl is not None and hasattr(impl, fn_name):
        try:
            fn = getattr(impl, fn_name)
            return fn(*args, **kwargs)
        except Exception:
            logger.error("Error calling %s", fn_name, exc_info=True)
            return default
    logger.error("inbox_drag implementation missing: %s", fn_name)
    return default


def build_draggable_items_html(items: List[Dict[str, Any]]) -> str:
    """Proxy to build_draggable_items_html implementation.

    Returns an HTML string or empty string on failure.
    """
    return _call_or_default("build_draggable_items_html", items, default="")


def build_calendar_drop_html(date: str = "2025-01-01", start_hour: int = 9, end_hour: int = 21) -> str:
    """Proxy to build_calendar_drop_html implementation.

    Returns calendar HTML or empty string on failure.
    """
    return _call_or_default("build_calendar_drop_html", date, start_hour, end_hour, default="")


def build_drag_and_drop_js(calendar_id: str = "inbox-drop-calendar") -> str:
    """Proxy to build_drag_and_drop_js implementation.

    Returns JS snippet or empty string on failure.
    """
    return _call_or_default("build_drag_and_drop_js", calendar_id, default="")


def process_drag_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Proxy to process_drag_payload implementation.

    Returns the implementation result or a failure dict when missing.
    """
    return _call_or_default("process_drag_payload", payload, default={"success": False, "error": "inbox_drag implementation missing"})


def handle_query_params(st_module: Optional[Any] = None) -> Dict[str, Any]:
    """Proxy to handle_query_params implementation.

    Accepts optional st_module to facilitate testing.
    """
    return _call_or_default("handle_query_params", st_module, default={"success": False, "error": "inbox_drag implementation missing"})


__all__ = [
    "build_draggable_items_html",
    "build_calendar_drop_html",
    "build_drag_and_drop_js",
    "process_drag_payload",
    "handle_query_params",
]
