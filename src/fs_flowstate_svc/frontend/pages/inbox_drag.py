import logging
import asyncio
import inspect
import json
from typing import Any, Dict, List, Optional

from fs_flowstate_svc.frontend import auth_utils
from fs_flowstate_svc.schemas.inbox_schemas import InboxItemConvertToEvent

logger = logging.getLogger(__name__)


def _safe_run_coro(maybe_awaitable: Any) -> Any:
    """Run coroutine or return sync result. Handles existing event loop cases."""
    try:
        if inspect.isawaitable(maybe_awaitable):
            try:
                return asyncio.run(maybe_awaitable)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(maybe_awaitable)
                finally:
                    try:
                        loop.close()
                    except Exception:
                        pass
        return maybe_awaitable
    except Exception as e:
        logger.error(e, exc_info=True)
        return None


def _get_st():
    """Return streamlit module if available, otherwise fall back to auth_utils.st shim."""
    try:
        import streamlit as st  # type: ignore
        return st
    except Exception:
        # Tests provide a shimmed st in auth_utils
        try:
            return auth_utils.st
        except Exception:
            return None


def build_draggable_items_html(items: List[Dict[str, Any]]) -> str:
    """Return a minimal HTML snippet rendering inbox items as draggable elements."""
    try:
        parts: List[str] = [
            "<div class=\"inbox-draggable-list\">"
        ]
        for it in items:
            iid = str(it.get("id", ""))
            content = str(it.get("content", "")).replace('"', '&quot;')
            category = str(it.get("category", ""))
            priority = str(it.get("priority", ""))
            # basic item html
            parts.append(
                f'<div class="inbox-draggable-item" draggable="true" '
                f'data-item-id="{iid}" data-content="{content}" data-category="{category}" data-priority="{priority}">'
                f"{content}</div>"
            )
        parts.append("</div>")
        return "\n".join(parts)
    except Exception as e:
        logger.error(e, exc_info=True)
        return ""


def build_calendar_drop_html(date: str = "2025-01-01", start_hour: int = 9, end_hour: int = 21) -> str:
    """Build a simple calendar drop target HTML grid.

    The HTML includes data attributes used by client-side JS (date, start/end hour).
    """
    try:
        hours = list(range(start_hour, end_hour))
        parts: List[str] = [
            f'<div id="inbox-drop-calendar" class="inbox-drop-calendar" data-date="{date}" data-start-hour="{start_hour}" data-end-hour="{end_hour}" style="border:1px solid #ddd;padding:8px; max-width:600px;">',
            '<style>.inbox-drop-calendar .slot{border-top:1px dashed #eee;padding:8px;height:40px;}</style>'
        ]
        for h in hours:
            parts.append(f'<div class="slot" data-hour="{h}">{h:02d}:00</div>')
        parts.append("</div>")
        return "\n".join(parts)
    except Exception as e:
        logger.error(e, exc_info=True)
        return ""


def build_drag_and_drop_js(calendar_id: str = "inbox-drop-calendar") -> str:
    """Return a JS snippet that wires simple dragstart/dragover/drop handlers.

    This JS computes a start_time and end_time based on the slot dropped onto,
    builds a JSON payload, encodes it and updates the location.search query param
    drag_payload to trigger a Streamlit rerun with the payload.

    Note: This JS is injected into Streamlit via st.markdown(unsafe_allow_html=True) when used in the real UI.
    """
    try:
        js = f"""
<script>
(function(){
  function nearestSlot(el, y){
    // if dropping on a slot element, use its data-hour
    try{{
      var slot = el.closest('.slot');
      if(slot && slot.dataset && slot.dataset.hour){{
        var h = parseInt(slot.dataset.hour,10);
        return {{hour:h}};
      }}
    }}catch(e){{}}
    return null;
  }

  document.addEventListener('dragstart', function(ev){
    var tgt = ev.target;
    if(!tgt || !tgt.classList.contains('inbox-draggable-item')) return;
    var payload = {{
      item_id: tgt.dataset.itemId,
      content: tgt.dataset.content,
      category: tgt.dataset.category,
      priority: tgt.dataset.priority
    }};
    ev.dataTransfer.setData('text/plain', JSON.stringify(payload));
  });

  var cal = document.getElementById('{calendar_id}');
  if(!cal) return;
  cal.addEventListener('dragover', function(ev){ ev.preventDefault(); });
  cal.addEventListener('drop', function(ev){
    ev.preventDefault();
    try{{
      var raw = ev.dataTransfer.getData('text/plain');
      var item = JSON.parse(raw || '{{}}');
      var slotInfo = nearestSlot(ev.target, ev.clientY) || {{hour: parseInt(cal.dataset.startHour || '9',10)}};
      var startHour = slotInfo.hour;
      // default duration 1 hour
      var endHour = startHour + 1;
      var date = cal.dataset.date || new Date().toISOString().slice(0,10);
      function iso(dtHour){
        return date + 'T' + (('0'+dtHour).slice(-2)) + ':00:00Z';
      }
      var payload = {{
        item_id: item.item_id || item.id,
        start_time: iso(startHour),
        end_time: iso(endHour),
        event_title: item.content || '',
        event_category: item.category || ''
      }};
      var encoded = encodeURIComponent(JSON.stringify(payload));
      // set query param to trigger Streamlit rerun
      var newQuery = '?drag_payload=' + encoded;
      window.history.replaceState(null, '', newQuery);
      window.location.reload();
    }}catch(e){{
      console.error(e);
    }}
  });
})();
</script>
"""
        return js
    except Exception as e:
        logger.error(e, exc_info=True)
        return ""


def process_drag_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process a drag payload by calling backend convert API and updating cache.

    Expected payload keys: item_id, start_time (ISO), end_time (ISO). Optional: event_title, event_category, event_description
    """
    try:
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")

        item_id = payload.get("item_id") or payload.get("id")
        start_time = payload.get("start_time")
        end_time = payload.get("end_time")

        if not item_id or not start_time or not end_time:
            raise ValueError("payload missing required keys: item_id/start_time/end_time")

        # attempt to find inbox item content/category from session cache to provide sensible defaults
        item_content: Optional[str] = None
        item_category: Optional[str] = None
        try:
            st = _get_st()
            cache = (st.session_state.get("inbox_items_cache", []) if st is not None else []) or []
            for it in cache:
                if str(it.get("id")) == str(item_id):
                    item_content = it.get("content") or item_content
                    item_category = it.get("category") or item_category
                    break
        except Exception:
            # ignore lookup errors
            logger.debug("Failed reading inbox_items_cache", exc_info=True)

        payload_to_send: Dict[str, Any] = {
            "item_id": item_id,
            "start_time": start_time,
            "end_time": end_time,
        }
        # defaults
        if payload.get("event_title"):
            payload_to_send["event_title"] = payload.get("event_title")
        elif item_content:
            payload_to_send["event_title"] = item_content

        if payload.get("event_description"):
            payload_to_send["event_description"] = payload.get("event_description")
        elif item_content and len(str(item_content)) <= 255:
            payload_to_send["event_description"] = item_content

        if payload.get("event_category"):
            payload_to_send["event_category"] = payload.get("event_category")
        elif item_category:
            payload_to_send["event_category"] = item_category

        # include metadata if provided
        if payload.get("event_metadata") is not None:
            payload_to_send["event_metadata"] = payload.get("event_metadata")

        # call backend via auth_utils
        try:
            result = _safe_run_coro(
                auth_utils._api_request("POST", "/api/inbox/convert_to_event", headers=auth_utils.get_auth_headers(), json=payload_to_send)
            )
        except Exception as e:
            logger.error(e, exc_info=True)
            return {"success": False, "error": str(e)}

        if not result or not result.get("success"):
            err = (result or {}).get("error") if isinstance(result, dict) else "Unknown error"
            logger.error(f"Conversion API failed: {err}")
            return {"success": False, "error": err}

        # On success, update session cache: set status to SCHEDULED
        try:
            st = _get_st()
            cache = (st.session_state.get("inbox_items_cache", []) if st is not None else []) or []
            updated = False
            for idx, it in enumerate(cache):
                if str(it.get("id")) == str(item_id):
                    try:
                        cache[idx]["status"] = "SCHEDULED"
                    except Exception:
                        # fallback replace whole entry
                        new = dict(it)
                        new["status"] = "SCHEDULED"
                        cache[idx] = new
                    updated = True
                    break
            if updated and st is not None:
                st.session_state["inbox_items_cache"] = cache
        except Exception as e:
            logger.error(e, exc_info=True)

        return {"success": True, "data": result.get("data")}

    except Exception as e:
        logger.error(e, exc_info=True)
        return {"success": False, "error": str(e)}


def handle_query_params(st_module: Optional[Any] = None) -> Dict[str, Any]:
    """Check streamlit query params for a drag_payload and process it.

    This helper allows the inbox page to integrate by calling handle_query_params()
    during render/startup. It will clear the drag_payload param after processing.
    """
    try:
        st = st_module if st_module is not None else _get_st()
        if st is None:
            return {"success": False, "error": "no streamlit available"}

        qp = {}
        try:
            qp = st.experimental_get_query_params() or {}
        except Exception:
            qp = {}

        raw = None
        if "drag_payload" in qp:
            v = qp.get("drag_payload")
            # Streamlit may provide list or string
            if isinstance(v, list) and len(v) > 0:
                raw = v[0]
            elif isinstance(v, str):
                raw = v
        if not raw:
            return {"success": False, "error": "no drag_payload"}

        try:
            # raw might be urlencoded
            try:
                from urllib.parse import unquote
                s = unquote(raw)
            except Exception:
                s = raw
            payload = json.loads(s)
        except Exception as e:
            logger.error(e, exc_info=True)
            return {"success": False, "error": "invalid payload"}

        res = process_drag_payload(payload)

        # clear query params to avoid reprocessing
        try:
            st.experimental_set_query_params()
        except Exception:
            pass

        return res
    except Exception as e:
        logger.error(e, exc_info=True)
        return {"success": False, "error": str(e)}


__all__ = [
    "build_draggable_items_html",
    "build_calendar_drop_html",
    "build_drag_and_drop_js",
    "process_drag_payload",
    "handle_query_params",
]
