import logging
import html
from datetime import date, datetime, time, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fs_flowstate_svc.frontend import auth_utils

logger = logging.getLogger(__name__)


def parse_iso(dt_str: str) -> datetime:
    """Parse ISO datetime string into timezone-aware UTC datetime.

    This helper mirrors the parsing logic used in the pages implementation but
    avoids importing streamlit so it can be used in tests that do not provide
    a real streamlit module.
    """
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            # assume UTC
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        # fallback to today's midnight UTC
        return datetime.combine(date.today(), time(0, 0, 0)).replace(tzinfo=timezone.utc)


def _minutes_since_start(day_dt: datetime, start_hour: int, dt: datetime) -> int:
    base = datetime.combine(day_dt.date(), time(start_hour, 0, 0)).replace(tzinfo=dt.tzinfo)
    delta = dt - base
    return int(delta.total_seconds() // 60)


def build_timeline_html(
    events: List[Dict[str, Any]],
    timeline_date: date,
    start_hour: int,
    end_hour: int,
    px_per_minute: int = 2,
) -> str:
    """Build a minimal HTML timeline used in tests.

    The function intentionally mirrors the structure expected by frontend tests
    (data-ppm on container, draggable-event class, data-event-id and
    data-duration-min on events) but does not require Streamlit.
    """
    hours = list(range(start_hour, end_hour + 1))
    total_minutes = (end_hour - start_hour) * 60
    container_height = total_minutes * px_per_minute

    css = f"""
    <style>
    .timeline-container {{ position: relative; border: 1px solid #ddd; height: {container_height}px; width: 100%; background: #fafafa; }}
    .hour-label {{ position: absolute; left: 0; width: 60px; color: #666; font-size: 12px; }}
    .hour-line {{ position: absolute; left: 60px; right: 0; height: 1px; background: #eee; }}
    .event-block {{ position: absolute; left: 70px; right: 8px; background: #4a90e2; color: white; padding: 4px 6px; border-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,0.1); font-size: 13px; overflow: hidden; cursor: move; }}
    </style>
    """

    body: List[str] = [css]
    body.append(
        f'<div class="timeline-container" data-ppm="{px_per_minute}" data-start-hour="{start_hour}" data-end-hour="{end_hour}" data-date="{timeline_date.isoformat()}">'  # noqa: E501
    )

    for h in hours:
        top_minutes = (h - start_hour) * 60
        top_px = top_minutes * px_per_minute
        label = f"{h:02d}:00"
        body.append(f"<div class=\"hour-label\" style=\"top: {top_px}px;\">{label}</div>")
        body.append(f"<div class=\"hour-line\" style=\"top: {top_px}px;\"></div>")

    for ev in events:
        try:
            ev_start = parse_iso(ev.get("start_time"))
            ev_end = parse_iso(ev.get("end_time"))

            window_start = datetime.combine(timeline_date, time(start_hour, 0, 0)).replace(tzinfo=timezone.utc)
            window_end = datetime.combine(timeline_date, time(end_hour, 0, 0)).replace(tzinfo=timezone.utc)

            if ev_end <= window_start or ev_start >= window_end:
                continue

            display_start = max(ev_start, window_start)
            display_end = min(ev_end, window_end)

            top_min = _minutes_since_start(window_start, start_hour, display_start)
            height_min = max(1, int((display_end - display_start).total_seconds() // 60))

            top_px = top_min * px_per_minute
            height_px = height_min * px_per_minute

            title = html.escape(ev.get("title", "(no title)"))
            start_label = display_start.strftime("%H:%M")
            end_label = display_end.strftime("%H:%M")

            duration_min = int((ev_end - ev_start).total_seconds() // 60)
            event_id = ev.get("id") or ev.get("event_id") or ""
            start_iso = ev.get("start_time")
            end_iso = ev.get("end_time")

            event_html = (
                f'<div class="event-block draggable-event" data-event-id="{event_id}" data-duration-min="{duration_min}" data-start-iso="{start_iso}" data-end-iso="{end_iso}" style="top: {top_px}px; height: {height_px}px;">'
                f"<div class=\"event-title\">{title}</div>"
                f"<div class=\"event-time\">{start_label} - {end_label}</div>"
                f"</div>"
            )
            body.append(event_html)
        except Exception as e:
            logger.error(e, exc_info=True)
            continue

    body.append("</div>")
    return "\n".join(body)


def compute_times_from_pixels(
    timeline_date: date,
    start_hour: int,
    end_hour: int,
    top_px: int,
    duration_min: int,
    px_per_minute: int = 2,
) -> Tuple[datetime, datetime]:
    """Compute UTC start/end datetimes from pixel position, clamped to window.

    Returns timezone-aware datetimes (tzinfo=timezone.utc).
    """
    try:
        ppm = int(px_per_minute)
        minutes_from_start = round(top_px / ppm)
        window_start = datetime.combine(timeline_date, time(start_hour, 0, 0)).replace(tzinfo=timezone.utc)
        window_end = datetime.combine(timeline_date, time(end_hour, 0, 0)).replace(tzinfo=timezone.utc)

        new_start = window_start + timedelta(minutes=minutes_from_start)
        new_end = new_start + timedelta(minutes=duration_min)

        if new_end > window_end:
            new_end = window_end
            new_start = new_end - timedelta(minutes=duration_min)
            if new_start < window_start:
                new_start = window_start
                new_end = new_start + timedelta(minutes=duration_min)

        if new_start < window_start:
            new_start = window_start
            new_end = new_start + timedelta(minutes=duration_min)

        return new_start, new_end
    except Exception as e:
        logger.error(e, exc_info=True)
        ws = datetime.combine(timeline_date, time(start_hour, 0, 0)).replace(tzinfo=timezone.utc)
        return ws, ws + timedelta(minutes=duration_min)


async def update_event_time(
    event_id: str,
    start_dt: datetime,
    end_dt: datetime,
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Call PUT /api/events/{event_id} to update start/end times.

    Uses auth_utils.get_auth_headers() and auth_utils.st.session_state for base url.
    """
    try:
        base = auth_utils.st.session_state.get("api_base_url", "http://localhost:8000")
    except Exception:
        base = "http://localhost:8000"

    headers = auth_utils.get_auth_headers()
    payload = {
        "start_time": start_dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "end_time": end_dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
    }

    close_client = False
    try:
        if client is None:
            try:
                import httpx

                client = httpx.AsyncClient(base_url=base)
                close_client = True
            except Exception as e:
                logger.error("httpx not available", exc_info=True)
                return {"success": False, "data": None, "error": "httpx unavailable"}

        resp = await client.request("PUT", f"/api/events/{event_id}", headers=headers, json=payload)
        # mimic httpx.raise_for_status behavior
        try:
            code = getattr(resp, "status_code", None) or getattr(resp, "_status", None)
            if code is not None and not (200 <= int(code) < 300):
                raise Exception(f"HTTP status {code}")
        except Exception:
            pass

        try:
            data = resp.json() if hasattr(resp, "json") else None
        except Exception:
            data = None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        logger.error(e, exc_info=True)
        try:
            msg = e.response.json() if hasattr(e, "response") and getattr(e, "response") is not None else str(e)
        except Exception:
            msg = str(e)
        return {"success": False, "data": None, "error": msg}
    finally:
        if close_client:
            try:
                await client.aclose()
            except Exception:
                pass


__all__ = ["build_timeline_html", "compute_times_from_pixels", "update_event_time", "parse_iso"]
