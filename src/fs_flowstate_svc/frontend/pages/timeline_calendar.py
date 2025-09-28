import asyncio
import logging
import html
from datetime import date, datetime, time, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple

import streamlit as st
from fs_flowstate_svc.frontend import auth_utils

logger = logging.getLogger(__name__)


async def fetch_events_for_range(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Fetch events for the current user between start_date and end_date (YYYY-MM-DD).

    Returns list of event dicts or empty list on error.
    """
    base = st.session_state.get("api_base_url", "http://localhost:8000")
    headers = auth_utils.get_auth_headers()
    try:
        async with __import__("httpx").AsyncClient(base_url=base) as client:  # local import to avoid top-level requirement
            resp = await client.get(
                "/api/events/",
                params={"start_date": start_date, "end_date": end_date},
                headers=headers,
            )
            resp.raise_for_status()
            try:
                return resp.json() or []
            except Exception:
                return []
    except Exception as e:
        logger.error(e, exc_info=True)
        return []


def parse_iso(dt_str: str) -> datetime:
    """Parse an ISO formatted datetime string into a naive UTC datetime.

    Accepts trailing Z and converts any offset-aware datetimes to naive UTC for comparisons.
    """
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(dt_str)
        # Normalize offset-aware datetimes to naive UTC to avoid tz comparison issues
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        # fallback: try a second time and ensure naive
        try:
            dt = datetime.fromisoformat(dt_str)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            # return today's start as safe fallback
            return datetime.combine(date.today(), time(0, 0, 0))


def _minutes_since_start(day_dt: datetime, start_hour: int, dt: datetime) -> int:
    """Compute minutes offset from start_hour on the same day for dt."""
    base = datetime.combine(day_dt.date(), time(start_hour, 0, 0))
    delta = dt - base
    return int(delta.total_seconds() // 60)


def build_timeline_html(
    events: List[Dict[str, Any]],
    timeline_date: date,
    start_hour: int,
    end_hour: int,
    px_per_minute: int = 2,
) -> str:
    """Build an HTML representation of a vertical timeline and events.

    Adds data attributes and draggable class for client-side drag-and-drop.
    This function is pure and testable.
    """
    hours = list(range(start_hour, end_hour + 1))
    total_minutes = (end_hour - start_hour) * 60
    container_height = total_minutes * px_per_minute

    # CSS - use normal string concatenation to avoid f-string brace evaluation
    css = (
        "<style>\n"
        ".timeline-container { position: relative; border: 1px solid #ddd; height: "
        + str(container_height)
        + "px; width: 100%; background: #fafafa; }\n"
        ".hour-label { position: absolute; left: 0; width: 60px; color: #666; font-size: 12px; }\n"
        ".hour-line { position: absolute; left: 60px; right: 0; height: 1px; background: #eee; }\n"
        ".event-block { position: absolute; left: 70px; right: 8px; background: #4a90e2; color: white; padding: 4px 6px; border-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,0.1); font-size: 13px; overflow: hidden; cursor: move; }\n"
        ".event-title { font-weight: 600; }\n"
        ".event-time { font-size: 11px; opacity: 0.9; }\n"
        "/* simple visual for dragging */\n"
        ".dragging { opacity: 0.8; box-shadow: 0 4px 8px rgba(0,0,0,0.2); transform: scale(1.01); }\n"
        "</style>\n"
    )

    # Build hour grid
    body = [css, f"<div class=\"timeline-container\" data-ppm=\"{px_per_minute}\" data-start-hour=\"{start_hour}\" data-end-hour=\"{end_hour}\" data-date=\"{timeline_date.isoformat()}\">"]
    for h in hours:
        top_minutes = (h - start_hour) * 60
        top_px = top_minutes * px_per_minute
        label = f"{h:02d}:00"
        body.append(f"<div class=\"hour-label\" style=\"top: {top_px}px;\">{label}</div>")
        body.append(f"<div class=\"hour-line\" style=\"top: {top_px}px;\"></div>")

    # Render events
    for ev in events:
        try:
            ev_start = parse_iso(ev.get("start_time"))
            ev_end = parse_iso(ev.get("end_time"))
            # Clip to displayed window
            window_start = datetime.combine(timeline_date, time(start_hour, 0, 0))
            window_end = datetime.combine(timeline_date, time(end_hour, 0, 0))
            if ev_end <= window_start or ev_start >= window_end:
                continue  # outside

            # Clamp
            display_start = max(ev_start, window_start)
            display_end = min(ev_end, window_end)

            top_min = _minutes_since_start(window_start, start_hour, display_start)
            height_min = max(1, int((display_end - display_start).total_seconds() // 60))

            top_px = top_min * px_per_minute
            height_px = height_min * px_per_minute

            title = html.escape(ev.get("title", "(no title)"))
            start_label = display_start.strftime("%H:%M")
            end_label = display_end.strftime("%H:%M")

            # compute duration minutes for data attribute
            duration_min = int((ev_end - ev_start).total_seconds() // 60)
            event_id = ev.get("id") or ev.get("event_id") or ""
            start_iso = ev.get("start_time")
            end_iso = ev.get("end_time")

            event_html = (
                f"<div class=\"event-block draggable-event\" data-event-id=\"{event_id}\" data-duration-min=\"{duration_min}\" data-start-iso=\"{start_iso}\" data-end-iso=\"{end_iso}\" style=\"top: {top_px}px; height: {height_px}px;\">"
                f"<div class=\"event-title\">{title}</div>"
                f"<div class=\"event-time\">{start_label} - {end_label}</div>"
                f"</div>"
            )
            body.append(event_html)
        except Exception as e:
            logger.error(e, exc_info=True)
            continue

    # Simple JS to enable client-side drag detection and triggering a rerun via query param
    # Note: In tests this JS is not executed. It provides the expected integration for browsers.
    js = """
    <script>
    (function(){
      try{
        const container = document.querySelector('.timeline-container');
        if(!container) return;
        const ppm = parseFloat(container.getAttribute('data-ppm') || '2');
        const startHour = parseInt(container.getAttribute('data-start-hour') || '0');
        const dateStr = container.getAttribute('data-date');
        let draggingEl = null;
        let offsetY = 0;

        function onMouseDown(e){
          const el = e.target.closest('.draggable-event');
          if(!el) return;
          draggingEl = el;
          el.classList.add('dragging');
          offsetY = e.clientY - el.getBoundingClientRect().top;
          document.addEventListener('mousemove', onMouseMove);
          document.addEventListener('mouseup', onMouseUp);
          e.preventDefault();
        }

        function onMouseMove(e){
          if(!draggingEl) return;
          const containerRect = container.getBoundingClientRect();
          let top = e.clientY - containerRect.top - offsetY;
          top = Math.max(0, Math.min(top, containerRect.height - draggingEl.offsetHeight));
          draggingEl.style.top = top + 'px';
        }

        function onMouseUp(e){
          if(!draggingEl) return;
          const el = draggingEl;
          draggingEl = null;
          el.classList.remove('dragging');
          document.removeEventListener('mousemove', onMouseMove);
          document.removeEventListener('mouseup', onMouseUp);

          const topPx = parseFloat(el.style.top.replace('px','')) || 0;
          const durationMin = parseInt(el.getAttribute('data-duration-min') || '0');
          const eventId = el.getAttribute('data-event-id');
          // compute minutes from start
          const minutesFromStart = Math.round(topPx / ppm);
          const startDate = new Date(dateStr + 'T00:00:00Z');
          startDate.setUTCHours(startHour, 0, 0, 0);
          const newStart = new Date(startDate.getTime() + minutesFromStart * 60000);
          const newEnd = new Date(newStart.getTime() + durationMin * 60000);

          const payload = {event_id: eventId, start_time: newStart.toISOString(), end_time: newEnd.toISOString()};
          // encode in query param and reload to trigger streamlit rerun
          const q = encodeURIComponent(JSON.stringify(payload));
          try{
            const url = new URL(window.location.href);
            url.searchParams.set('drag', q);
            window.location.href = url.toString();
          }catch(err){
            console.error(err);
          }
        }

        document.addEventListener('mousedown', onMouseDown);
      }catch(e){console.error(e);}
    })();
    </script>
    """

    body.append(js)

    body.append("</div>")
    return "\n".join(body)


# Helper: compute times from pixels - pure and testable
def compute_times_from_pixels(
    timeline_date: date,
    start_hour: int,
    end_hour: int,
    top_px: int,
    duration_min: int,
    px_per_minute: int = 2,
) -> Tuple[datetime, datetime]:
    """Compute timezone-aware UTC start and end datetimes from pixel position.

    Clamps to timeline window and preserves duration.
    Returns datetime objects with timezone.utc tzinfo.
    """
    try:
        ppm = int(px_per_minute)
        minutes_from_start = round(top_px / ppm)
        window_start = datetime.combine(timeline_date, time(start_hour, 0, 0)).replace(tzinfo=timezone.utc)
        window_end = datetime.combine(timeline_date, time(end_hour, 0, 0)).replace(tzinfo=timezone.utc)

        new_start = window_start + timedelta(minutes=minutes_from_start)
        new_end = new_start + timedelta(minutes=duration_min)

        # clamp if exceeds window_end
        if new_end > window_end:
            # shift start so end == window_end
            new_end = window_end
            new_start = new_end - timedelta(minutes=duration_min)
            if new_start < window_start:
                new_start = window_start
                new_end = new_start + timedelta(minutes=duration_min)
        # ensure not before window_start
        if new_start < window_start:
            new_start = window_start
            new_end = new_start + timedelta(minutes=duration_min)

        return new_start, new_end
    except Exception as e:
        logger.error(e, exc_info=True)
        # fallback: return window start to start+duration
        ws = datetime.combine(timeline_date, time(start_hour, 0, 0)).replace(tzinfo=timezone.utc)
        return ws, ws + timedelta(minutes=duration_min)


async def update_event_time(
    event_id: str,
    start_dt: datetime,
    end_dt: datetime,
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Call PUT /api/events/{event_id} to update event times.

    Returns structured result dict.
    """
    base = st.session_state.get("api_base_url", "http://localhost:8000")
    headers = auth_utils.get_auth_headers()
    payload = {
        "start_time": start_dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "end_time": end_dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    }
    close_client = False
    try:
        if client is None:
            client = __import__("httpx").AsyncClient(base_url=base)
            close_client = True

        resp = await client.request("PUT", f"/api/events/{event_id}", headers=headers, json=payload)
        resp.raise_for_status()
        try:
            data = resp.json()
        except Exception:
            data = None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        logger.error(e, exc_info=True)
        # try to extract message if httpx
        try:
            msg = e.response.json() if hasattr(e, 'response') and e.response is not None else str(e)
        except Exception:
            msg = str(e)
        return {"success": False, "data": None, "error": msg}
    finally:
        if close_client:
            try:
                await client.aclose()
            except Exception:
                pass


async def process_drag_payload(payload: Dict[str, Any], client: Optional[Any] = None) -> Dict[str, Any]:
    """Process drag payload (expects event_id, start_time and end_time in ISO) and call update_event_time.

    Payload may alternatively contain pixel info; this function handles the simple ISO case used by injected JS.
    """
    try:
        if not isinstance(payload, dict):
            logger.error("Invalid drag payload: not a dict")
            return {"success": False, "error": "invalid payload"}

        event_id = payload.get("event_id")
        start_iso = payload.get("start_time")
        end_iso = payload.get("end_time")
        if not event_id or not start_iso or not end_iso:
            logger.error("Invalid drag payload: missing keys")
            return {"success": False, "error": "missing keys"}

        # parse to timezone-aware UTC datetimes
        try:
            start_dt = datetime.fromisoformat(start_iso.replace('Z', '+00:00')).astimezone(timezone.utc)
            end_dt = datetime.fromisoformat(end_iso.replace('Z', '+00:00')).astimezone(timezone.utc)
        except Exception:
            logger.error("Failed to parse ISO datetimes from payload")
            return {"success": False, "error": "failed to parse datetimes"}

        return await update_event_time(event_id, start_dt, end_dt, client=client)
    except Exception as e:
        logger.error(e, exc_info=True)
        return {"success": False, "error": str(e)}


# Page render executed on import
def _render():
    st.set_page_config(page_title="Timeline Calendar")

    # Defaults
    start_hour = st.session_state.get("start_hour", 9)
    end_hour = st.session_state.get("end_hour", 21)
    timeline_date = st.session_state.get("timeline_date", date.today())

    # store back defaults in session_state so tests can modify prior to import
    st.session_state.setdefault("start_hour", start_hour)
    st.session_state.setdefault("end_hour", end_hour)
    st.session_state.setdefault("timeline_date", timeline_date)

    # If a drag payload exists in query params, attempt to process it
    try:
        query = getattr(st, 'experimental_get_query_params', None)
        drag_raw = None
        if callable(query):
            try:
                q = st.experimental_get_query_params()
                drag_param = q.get('drag') if isinstance(q, dict) else None
                if drag_param:
                    # Streamlit returns list values for query params
                    drag_raw = drag_param[0] if isinstance(drag_param, list) else drag_param
                    # decode and parse
                    import urllib.parse, json
                    try:
                        decoded = urllib.parse.unquote(drag_raw)
                        payload = json.loads(decoded)
                        # process asynchronously
                        try:
                            asyncio.run(process_drag_payload(payload))
                        except Exception:
                            # swallowing errors to not break page render
                            logger.error('Error processing drag payload', exc_info=True)
                    except Exception:
                        logger.error('Invalid drag query param', exc_info=True)
            except Exception:
                pass
    except Exception:
        # Query param helpers may not exist; ignore
        pass

    if not auth_utils.is_logged_in():
        st.markdown("<p>Please log in to view your timeline.</p>", unsafe_allow_html=True)
        return

    # Fetch events for the displayed date
    start_date = timeline_date.isoformat()
    end_date = timeline_date.isoformat()

    # Allow tests to disable automatic network fetch at import by setting session_state['auto_fetch'] = False
    auto_fetch = st.session_state.get("auto_fetch", True)
    if auto_fetch:
        try:
            events = asyncio.run(fetch_events_for_range(start_date, end_date))
        except Exception as e:
            logger.error(e, exc_info=True)
            events = []
    else:
        events = []

    # Build HTML and render
    html_out = build_timeline_html(events, timeline_date, start_hour, end_hour, px_per_minute=2)
    st.markdown(html_out, unsafe_allow_html=True)


# execute when module imported
_render()
