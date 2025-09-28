import importlib
import sys
from types import SimpleNamespace

import pytest

from fs_flowstate_svc.frontend import auth_utils


class FakeStreamlit:
    def __init__(self):
        # simulate Streamlit session state
        self.session_state = {}
        self._inputs = {}
        self._form_submits = {}
        self._current_form = None
        self.markdowns = []
        self.writes = []
        self.dataframes = []
        self.errors = []
        self.successes = []
        self.set_page_config_called = False

    def set_page_config(self, **kwargs):
        self.set_page_config_called = True

    class _FormCtx:
        def __init__(self, parent, name):
            self.parent = parent
            self.name = name

        def __enter__(self):
            self.parent._current_form = self.name

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.parent._current_form = None

    def form(self, name):
        return FakeStreamlit._FormCtx(self, name)

    def text_input(self, label):
        return self._inputs.get(label, self.session_state.get("inbox_content", ""))

    def selectbox(self, label, options, index=0):
        # return either seeded input or default
        return self._inputs.get(label, options[index])

    def slider(self, label, min_value, max_value, value):
        return self._inputs.get(label, self.session_state.get("inbox_priority", value))

    def form_submit_button(self, label):
        return bool(self._form_submits.get(self._current_form, False))

    def markdown(self, content, unsafe_allow_html=False):
        self.markdowns.append(content)

    def write(self, msg):
        self.writes.append(msg)

    def dataframe(self, df):
        # capture a simple textual representation
        self.dataframes.append(df.to_dict(orient="records"))

    def error(self, msg):
        self.errors.append(msg)

    def success(self, msg):
        self.successes.append(msg)

    # New UI helpers used by inbox_page
    def checkbox(self, label, value=False, key=None):
        # key-aware; prefer explicit key in inputs then session_state
        if key is not None:
            return self._inputs.get(key, self.session_state.get(key, value))
        return self._inputs.get(label, value)

    def button(self, label, key=None):
        # consider key-based press simulation via _inputs or _form_submits
        if key is not None:
            return bool(self._inputs.get(key, False)) or bool(self._form_submits.get(key, False))
        return bool(self._inputs.get(label, False))


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
    module_name = "fs_flowstate_svc.frontend.pages.inbox_page"
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


def test_filter_triggers_get_with_query(fake_st, monkeypatch):
    fake_st.session_state["is_authenticated"] = True
    fake_st.session_state["access_token"] = "tok"

    # set filter inputs
    from fs_flowstate_svc.schemas.inbox_schemas import InboxCategory, InboxStatus

    fake_st._inputs["Filter Category"] = InboxCategory.TODO
    fake_st._inputs["Filter Status"] = InboxStatus.PENDING
    fake_st._inputs["Priority Min"] = 1
    fake_st._inputs["Priority Max"] = 3

    calls = {"last": None}

    def fake_api_request(method, url, client=None, headers=None, json=None):
        calls["last"] = {"method": method, "url": url, "json": json}
        # return empty list for GET
        if method == "GET":
            return {"success": True, "data": [], "error": None}
        return {"success": False, "data": None, "error": "unexpected"}

    monkeypatch.setattr(auth_utils, "_api_request", lambda *a, **k: fake_api_request(*a, **k))

    module = _import_page()
    # call render
    module._render()

    assert calls["last"] is not None
    assert calls["last"]["method"] == "GET"
    # query should include category, status, priority_min, priority_max
    assert "category=TODO" in calls["last"]["url"]
    assert "status=PENDING" in calls["last"]["url"]
    assert "priority_min=1" in calls["last"]["url"]
    assert "priority_max=3" in calls["last"]["url"]


def test_select_all_and_bulk_mark_done(fake_st, monkeypatch):
    fake_st.session_state["is_authenticated"] = True
    fake_st.session_state["access_token"] = "tok"
    # seed items in cache
    items = [
        {"id": "a1", "content": "c1", "category": "TODO", "priority": 2, "status": "PENDING"},
        {"id": "b2", "content": "c2", "category": "IDEA", "priority": 3, "status": "PENDING"},
    ]
    fake_st.session_state["inbox_items_cache"] = items
    # simulate select all
    fake_st.session_state["inbox_select_all"] = True
    # choose bulk action
    fake_st._inputs["Bulk Action"] = "Mark as Done"
    fake_st._form_submits["bulk_form"] = True

    calls = {"history": []}

    def fake_api_request(method, url, client=None, headers=None, json=None):
        calls["history"].append({"method": method, "url": url, "json": json})
        if method == "POST" and url == "/api/inbox/bulk/status":
            return {"success": True, "data": {"message": "2 items updated"}, "error": None}
        if method == "GET":
            return {"success": True, "data": items, "error": None}
        return {"success": False, "data": None, "error": "unexpected"}

    monkeypatch.setattr(auth_utils, "_api_request", lambda *a, **k: fake_api_request(*a, **k))

    module = _import_page()
    module._render()

    # ensure bulk POST called
    post_calls = [c for c in calls["history"] if c["method"] == "POST"]
    assert post_calls, "No POST calls made"
    assert post_calls[0]["url"] == "/api/inbox/bulk/status"
    assert set(post_calls[0]["json"]["item_ids"]) == {"a1", "b2"}
    assert post_calls[0]["json"]["new_status"] == "DONE"
    # after success, inbox_select_all should be cleared
    assert fake_st.session_state.get("inbox_select_all") is False


def test_edit_item_save_calls_put_and_updates_cache(fake_st, monkeypatch):
    fake_st.session_state["is_authenticated"] = True
    fake_st.session_state["access_token"] = "tok"
    item = {"id": "x1", "content": "orig", "category": "TODO", "priority": 3, "status": "PENDING"}
    fake_st.session_state["inbox_items_cache"] = [item]
    # set editing id
    fake_st.session_state["inbox_editing_id"] = "x1"
    # provide edited inputs
    fake_st._inputs[f"Edit Content - x1"] = "updated content"
    from fs_flowstate_svc.schemas.inbox_schemas import InboxCategory, InboxStatus
    fake_st._inputs[f"Edit Category - x1"] = InboxCategory.IDEA
    fake_st._inputs[f"Edit Priority - x1"] = 1
    fake_st._inputs[f"Edit Status - x1"] = InboxStatus.DONE
    fake_st._inputs[f"Edit Action - x1"] = "Save"
    fake_st._form_submits[f"edit_form_x1"] = True

    calls = {"history": []}

    def fake_api_request(method, url, client=None, headers=None, json=None):
        calls["history"].append({"method": method, "url": url, "json": json})
        if method == "PUT" and url == "/api/inbox/x1":
            updated = {"id": "x1", "content": json.get("content", "orig"), "category": json.get("category", "TODO"), "priority": json.get("priority", 3), "status": json.get("status", "PENDING")}
            return {"success": True, "data": updated, "error": None}
        if method == "GET":
            return {"success": True, "data": [item], "error": None}
        return {"success": False, "data": None, "error": "unexpected"}

    monkeypatch.setattr(auth_utils, "_api_request", lambda *a, **k: fake_api_request(*a, **k))

    module = _import_page()
    module._render()

    # ensure PUT called
    put_calls = [c for c in calls["history"] if c["method"] == "PUT"]
    assert put_calls, "No PUT calls made"
    assert put_calls[0]["url"] == "/api/inbox/x1"
    # payload should include changed fields
    assert put_calls[0]["json"]["content"] == "updated content"
    assert put_calls[0]["json"]["category"] == "IDEA"
    assert put_calls[0]["json"]["priority"] == 1
    assert put_calls[0]["json"]["status"] == "DONE"

    # cache should be updated
    cache = fake_st.session_state.get("inbox_items_cache")
    assert cache and cache[0]["content"] == "updated content"
    # editing id cleared
    assert fake_st.session_state.get("inbox_editing_id") is None
