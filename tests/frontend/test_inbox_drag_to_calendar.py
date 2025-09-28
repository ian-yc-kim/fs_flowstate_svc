import pytest
import json
from types import SimpleNamespace

from fs_flowstate_svc.frontend import inbox_drag
from fs_flowstate_svc.frontend import auth_utils


def test_build_draggable_html_contains_expected_attrs():
    items = [
        {"id": "itm-1", "content": "Meet client", "category": "TODO", "priority": 2},
        {"id": "itm-2", "content": "Plan", "category": "IDEA", "priority": 3},
    ]

    html_out = inbox_drag.build_draggable_items_html(items)
    assert 'draggable="true"' in html_out
    assert 'data-item-id="itm-1"' in html_out
    assert 'data-content="Meet client"' in html_out
    assert 'data-category="TODO"' in html_out
    assert 'data-priority="2"' in html_out


def test_build_calendar_html_and_js():
    cal_html = inbox_drag.build_calendar_drop_html(date="2025-01-01", start_hour=9, end_hour=12)
    assert 'inbox-drop-calendar' in cal_html
    assert 'data-date="2025-01-01"' in cal_html
    assert 'data-start-hour="9"' in cal_html or 'data-start-hour="09"' in cal_html
    js = inbox_drag.build_drag_and_drop_js()
    assert 'dragstart' in js
    assert 'drop' in js


def test_process_drag_payload_calls_api_and_updates_cache(monkeypatch):
    # ensure session_state exists via auth_utils shim
    st = auth_utils.st
    st.session_state = {}

    # seed cache with one pending item
    st.session_state["inbox_items_cache"] = [
        {"id": "itm-1", "content": "Meet client", "category": "TODO", "priority": 2, "status": "PENDING"}
    ]

    called = {}

    def fake_api_request(method, url, client=None, headers=None, json=None):
        called['method'] = method
        called['url'] = url
        called['json'] = json
        return {"success": True, "data": {"id": "evt-1"}, "error": None}

    monkeypatch.setattr(auth_utils, "_api_request", lambda *a, **k: fake_api_request(*a, **k))
    monkeypatch.setattr(auth_utils, "get_auth_headers", lambda: {"Authorization": "Bearer tok"})

    payload = {
        "item_id": "itm-1",
        "start_time": "2025-01-01T10:00:00Z",
        "end_time": "2025-01-01T11:00:00Z"
    }

    res = inbox_drag.process_drag_payload(payload)
    assert res.get("success") is True
    assert called.get('method') == 'POST'
    assert called.get('url') == '/api/inbox/convert_to_event'
    # payload forwarded should include item_id and times
    assert called.get('json')['item_id'] == 'itm-1'
    assert called.get('json')['start_time'] == '2025-01-01T10:00:00Z'
    assert called.get('json')['end_time'] == '2025-01-01T11:00:00Z'

    # cache updated to SCHEDULED
    cache = st.session_state.get('inbox_items_cache')
    assert cache[0]['status'] == 'SCHEDULED'


def test_handle_query_params_triggers_conversion(monkeypatch):
    st = auth_utils.st
    st.session_state = {}
    st.session_state["inbox_items_cache"] = [
        {"id": "itm-1", "content": "Meet client", "category": "TODO", "priority": 2, "status": "PENDING"}
    ]

    called = {}

    def fake_api_request(method, url, client=None, headers=None, json=None):
        called['method'] = method
        called['url'] = url
        called['json'] = json
        return {"success": True, "data": {"id": "evt-1"}, "error": None}

    monkeypatch.setattr(auth_utils, "_api_request", lambda *a, **k: fake_api_request(*a, **k))
    monkeypatch.setattr(auth_utils, "get_auth_headers", lambda: {"Authorization": "Bearer tok"})

    payload = {
        "item_id": "itm-1",
        "start_time": "2025-01-01T10:00:00Z",
        "end_time": "2025-01-01T11:00:00Z"
    }

    # simulate streamlit returning urlencoded payload as list
    from urllib.parse import quote
    raw = quote(json.dumps(payload))

    # provide experimental_get_query_params and experimental_set_query_params
    def fake_get_qp():
        return {"drag_payload": [raw]}

    def fake_set_qp(*a, **k):
        # clear called; don't need to do anything
        return None

    st.experimental_get_query_params = fake_get_qp
    st.experimental_set_query_params = fake_set_qp

    res = inbox_drag.handle_query_params(st_module=st)
    assert res.get('success') is True
    assert called.get('method') == 'POST'
    assert called.get('url') == '/api/inbox/convert_to_event'
    cache = st.session_state.get('inbox_items_cache')
    assert cache[0]['status'] == 'SCHEDULED'
