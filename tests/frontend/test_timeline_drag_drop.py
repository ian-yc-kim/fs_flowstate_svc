import asyncio
from datetime import date, datetime, timezone

import pytest

from fs_flowstate_svc.frontend import timeline_calendar
from fs_flowstate_svc.frontend import auth_utils


class DummyAsyncResp:
    def __init__(self, status_code=200, json_data=None):
        self._status = status_code
        self._json_data = json_data or {}

    def raise_for_status(self):
        if not (200 <= self._status < 300):
            # simulate httpx.HTTPStatusError minimally
            class Resp:
                def json(self):
                    return self._json_data

            raise Exception(f"HTTP status {self._status}")

    def json(self):
        return self._json_data


class DummyAsyncClient:
    def __init__(self, base_url=None):
        self.base_url = base_url
        self.requests = []

    async def request(self, method, url, headers=None, json=None):
        self.requests.append({"method": method, "url": url, "headers": headers, "json": json})
        return DummyAsyncResp(status_code=200, json_data={"ok": True})

    async def aclose(self):
        return None


def test_compute_times_preserves_duration_and_clamping():
    timeline_date = date(2024, 1, 15)
    start_hour = 9
    end_hour = 17
    ppm = 2
    duration_min = 120  # 2 hours

    # top_px at 0 => 9:00
    start_dt, end_dt = timeline_calendar.compute_times_from_pixels(timeline_date, start_hour, end_hour, 0, duration_min, px_per_minute=ppm)
    assert start_dt.hour == 9 and start_dt.tzinfo == timezone.utc
    assert int((end_dt - start_dt).total_seconds() // 60) == duration_min

    # top_px near end that would push end beyond 17:00 -> should clamp so end == 17:00
    # compute top_px that would give a start at 16:30 (which would end 18:30)
    top_px = (16 - start_hour) * 60 * ppm + 30 * ppm
    start2, end2 = timeline_calendar.compute_times_from_pixels(timeline_date, start_hour, end_hour, top_px, duration_min, px_per_minute=ppm)
    # clamped end should be 17:00
    assert end2.hour == 17 and end2.minute == 0
    # start should be 15:00 (17:00 - 2 hours)
    assert start2.hour == 15 and start2.minute == 0


def test_build_html_contains_draggable_attrs():
    events = [
        {
            "id": "evt-1",
            "title": "Meeting",
            "start_time": "2024-01-15T10:00:00Z",
            "end_time": "2024-01-15T11:30:00Z",
        }
    ]
    html_out = timeline_calendar.build_timeline_html(events, date(2024, 1, 15), 9, 21, px_per_minute=2)
    # container ppm attr
    assert 'data-ppm="2"' in html_out or "data-ppm='2'" in html_out
    # draggable class
    assert 'draggable-event' in html_out
    # data-event-id attribute
    assert 'data-event-id="evt-1"' in html_out
    # data-duration-min attribute (90 minutes)
    assert 'data-duration-min="90"' in html_out


def test_update_event_time_calls_put_and_persists(monkeypatch):
    # Setup session state and auth headers
    monkeypatch.setitem(auth_utils.st.session_state, 'api_base_url', 'http://testserver')
    # make get_auth_headers return a known header
    monkeypatch.setattr(auth_utils, 'get_auth_headers', lambda: {'Authorization': 'Bearer tok'})

    # patch httpx.AsyncClient with our DummyAsyncClient
    monkeypatch.setitem(__import__('builtins').__dict__, 'httpx', __import__('types'))
    # Instead of replacing httpx globally, we monkeypatch the AsyncClient constructor used in function

    async def fake_update():
        client = DummyAsyncClient(base_url='http://testserver')
        # call update_event_time with injected client
        start_dt = datetime(2024,1,15,10,0,tzinfo=timezone.utc)
        end_dt = datetime(2024,1,15,11,0,tzinfo=timezone.utc)
        result = await timeline_calendar.update_event_time('evt-123', start_dt, end_dt, client=client)
        # verify client recorded a PUT
        assert len(client.requests) == 1
        req = client.requests[0]
        assert req['method'] == 'PUT'
        assert req['url'] == '/api/events/evt-123'
        # payload iso strings with Z suffix
        assert req['json']['start_time'].endswith('Z')
        assert req['json']['end_time'].endswith('Z')
        assert result['success'] is True

    asyncio.run(fake_update())
