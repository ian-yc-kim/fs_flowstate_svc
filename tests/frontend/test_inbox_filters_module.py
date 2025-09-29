import pytest
from types import SimpleNamespace

from fs_flowstate_svc.schemas.inbox_schemas import InboxCategory, InboxPriority, InboxStatus
from fs_flowstate_svc.frontend import auth_utils
from fs_flowstate_svc.frontend.pages import inbox_filters


class DummySt:
    def __init__(self):
        self.session_state = {}


def test_build_query_with_multiselect_and_logic():
    filters = {
        "categories": [InboxCategory.TODO, InboxCategory.IDEA],
        "statuses": [InboxStatus.PENDING],
        "priorities": [InboxPriority.P1, InboxPriority.P3],
        "priority_min": 1,
        "priority_max": 5,
        "filter_logic": "OR",
    }

    q = inbox_filters.build_query_from_filters(filters)
    assert "categories=TODO,IDEA" in q
    assert "statuses=PENDING" in q
    # priorities should be represented by numeric values
    assert "priorities=1,3" in q
    # priority_min and priority_max must NOT appear because priorities list takes precedence
    assert "priority_min=" not in q
    assert "priority_max=" not in q
    assert "filter_logic=OR" in q


def test_priorities_override_min_max_edge_cases():
    # priorities as strings and enums mixed
    filters = {
        "priorities": ["1", InboxPriority.P4, 3],
        "priority_min": 2,
        "priority_max": 5,
    }
    q = inbox_filters.build_query_from_filters(filters)
    # expect priorities present
    assert "priorities=" in q
    assert "priority_min=" not in q
    assert "priority_max=" not in q


def test_ensure_defaults_and_clear_filters():
    st = DummySt()
    # initially empty
    inbox_filters.ensure_session_state_defaults(st)
    assert "inbox_filters" in st.session_state
    f = st.session_state["inbox_filters"]
    assert f["categories"] is None
    assert f["statuses"] is None
    assert f["priorities"] is None
    assert f["filter_logic"] == "AND"
    assert st.session_state.get("inbox_filters_applied") is None

    # set some values and clear
    st.session_state["inbox_filters"]["categories"] = [InboxCategory.NOTE]
    st.session_state["inbox_filters"]["priority_max"] = 4
    st.session_state["inbox_filters_applied"] = {"dummy": True}

    inbox_filters.clear_filters(st)
    f2 = st.session_state["inbox_filters"]
    assert f2["categories"] is None
    assert f2["priority_max"] is None
    assert st.session_state.get("inbox_filters_applied") is None


def test_fetch_items_with_filters_calls_api(monkeypatch):
    st = DummySt()
    # set filters
    st.session_state["inbox_filters"] = {"categories": [InboxCategory.TODO], "filter_logic": "AND"}

    captured = {"called": False, "url": None, "headers": None}

    def fake_get_auth_headers():
        return {"Authorization": "Bearer tok"}

    def fake_api_request(method, url, headers=None, json=None, client=None):
        captured["called"] = True
        captured["url"] = url
        captured["headers"] = headers
        return {"success": True, "data": [{"id": "1", "content": "x"}], "error": None}

    monkeypatch.setattr(auth_utils, "get_auth_headers", lambda: fake_get_auth_headers())
    monkeypatch.setattr(auth_utils, "_api_request", lambda *a, **k: fake_api_request(*a, **k))

    resp = inbox_filters.fetch_items_with_filters(st)
    assert captured["called"]
    assert "/api/inbox/" in captured["url"]
    assert "categories=TODO" in captured["url"]
    assert resp and resp.get("success")
    assert st.session_state.get("inbox_items_cache") is not None
