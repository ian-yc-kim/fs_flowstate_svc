import importlib
import sys
from types import SimpleNamespace
from datetime import date

import pytest

from fs_flowstate_svc.frontend import auth_utils


class FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.markdowns = []
        self.set_page_config_called = False

    def set_page_config(self, **kwargs):
        self.set_page_config_called = True

    def markdown(self, content, unsafe_allow_html=False):
        # capture rendered HTML/content for assertions
        self.markdowns.append(content)


@pytest.fixture(autouse=True)
def fake_st(monkeypatch):
    fake = FakeStreamlit()
    sys.modules["streamlit"] = fake
    # ensure auth_utils uses the same session_state object
    auth_utils.st = fake
    yield fake
    # cleanup
    try:
        del sys.modules["streamlit"]
    except Exception:
        pass
    auth_utils.st = getattr(auth_utils, "st", {})


def _import_page():
    if "fs_flowstate_svc.frontend.pages.timeline_calendar" in sys.modules:
        del sys.modules["fs_flowstate_svc.frontend.pages.timeline_calendar"]
    return importlib.import_module("fs_flowstate_svc.frontend.pages.timeline_calendar")


def test_shows_login_prompt_when_not_authenticated(fake_st):
    # ensure not logged in
    fake_st.session_state.clear()
    # import page (auto-render will show login prompt)
    _import_page()
    assert any("Please log in" in (m or "") for m in fake_st.markdowns)


def test_default_hours_rendered_when_authenticated(fake_st, monkeypatch):
    # set authenticated and disable auto fetch at import to avoid network calls
    fake_st.session_state["is_authenticated"] = True
    fake_st.session_state["access_token"] = "tok"
    fake_st.session_state["auto_fetch"] = False

    module = _import_page()

    async def fake_fetch(start, end):
        return []

    # patch the function on the imported module
    monkeypatch.setattr(module, "fetch_events_for_range", fake_fetch)
    # enable fetch and render
    fake_st.session_state["auto_fetch"] = True
    module._render()

    # first captured markdown is the timeline HTML
    assert any("09:00" in (m or "") for m in fake_st.markdowns)
    assert any("21:00" in (m or "") for m in fake_st.markdowns)
    assert not any("08:00" in (m or "") for m in fake_st.markdowns)


def test_single_event_rendering_position(fake_st, monkeypatch):
    fake_st.session_state["is_authenticated"] = True
    fake_st.session_state["access_token"] = "tok"
    # disable auto fetch at import
    fake_st.session_state["auto_fetch"] = False
    # set specific date
    fake_st.session_state["timeline_date"] = date(2024, 1, 15)

    module = _import_page()

    event = {
        "title": "Meeting",
        "start_time": "2024-01-15T10:00:00Z",
        "end_time": "2024-01-15T11:30:00Z",
    }

    async def fake_fetch(start, end):
        return [event]

    monkeypatch.setattr(module, "fetch_events_for_range", fake_fetch)
    fake_st.session_state["auto_fetch"] = True
    module._render()

    rendered = "\n".join(fake_st.markdowns)

    # title exists
    assert "Meeting" in rendered

    # Compute expected px with px_per_minute=2; start_hour default 9
    # top: 10:00 -> 60 minutes after 9:00 => 120px
    # height: 90 minutes => 180px
    assert "top: 120px" in rendered
    assert "height: 180px" in rendered


def test_multiple_non_overlapping_events(fake_st, monkeypatch):
    fake_st.session_state["is_authenticated"] = True
    fake_st.session_state["access_token"] = "tok"
    fake_st.session_state["auto_fetch"] = False
    fake_st.session_state["timeline_date"] = date(2024, 1, 15)

    module = _import_page()

    ev1 = {"title": "Ev1", "start_time": "2024-01-15T09:00:00Z", "end_time": "2024-01-15T10:00:00Z"}
    ev2 = {"title": "Ev2", "start_time": "2024-01-15T13:30:00Z", "end_time": "2024-01-15T14:00:00Z"}

    async def fake_fetch(start, end):
        return [ev1, ev2]

    monkeypatch.setattr(module, "fetch_events_for_range", fake_fetch)
    fake_st.session_state["auto_fetch"] = True
    module._render()

    rendered = "\n".join(fake_st.markdowns)

    assert "Ev1" in rendered
    assert "Ev2" in rendered

    # Ev1 top should be 0 minutes -> top 0px
    assert "top: 0px" in rendered
    # Ev2 top: 13:30 is 4.5 hours after 9 -> 270 minutes -> top 540px
    assert "top: 540px" in rendered


def test_configurable_hours_via_session_state(fake_st, monkeypatch):
    fake_st.session_state["is_authenticated"] = True
    fake_st.session_state["access_token"] = "tok"
    fake_st.session_state["start_hour"] = 8
    fake_st.session_state["end_hour"] = 20
    fake_st.session_state["auto_fetch"] = False

    module = _import_page()

    async def fake_fetch(start, end):
        return []

    monkeypatch.setattr(module, "fetch_events_for_range", fake_fetch)
    fake_st.session_state["auto_fetch"] = True
    module._render()

    rendered = "\n".join(fake_st.markdowns)

    assert "08:00" in rendered
    assert "20:00" in rendered
    assert "21:00" not in rendered


def test_no_events_renders_grid_only(fake_st, monkeypatch):
    fake_st.session_state["is_authenticated"] = True
    fake_st.session_state["access_token"] = "tok"
    fake_st.session_state["auto_fetch"] = False

    module = _import_page()

    async def fake_fetch(start, end):
        return []

    monkeypatch.setattr(module, "fetch_events_for_range", fake_fetch)
    fake_st.session_state["auto_fetch"] = True
    module._render()

    rendered = "\n".join(fake_st.markdowns)

    # event-block class should be present in CSS/html
    assert "event-block" in rendered
    assert "event-title" in rendered
