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


def test_shows_login_prompt_when_not_authenticated(fake_st):
    fake_st.session_state.clear()
    _import_page()
    assert any("Please log in" in (m or "") for m in fake_st.markdowns)


def test_create_item_success_clears_fields_and_updates_list(fake_st, monkeypatch):
    # ensure logged in and disable auto fetch at import time
    fake_st.session_state["is_authenticated"] = True
    fake_st.session_state["access_token"] = "tok"
    fake_st.session_state["auto_fetch"] = False

    # seed form inputs
    fake_st._inputs["Content"] = "Test quick capture"
    # selectbox option will be enum; place InboxCategory.TODO from real schema
    from fs_flowstate_svc.schemas.inbox_schemas import InboxCategory

    fake_st._inputs["Category"] = InboxCategory.TODO
    fake_st._inputs["Priority"] = 2
    fake_st._form_submits["inbox_form"] = True

    created_item = {
        "id": "itm-1",
        "content": "Test quick capture",
        "category": "TODO",
        "priority": 2,
        "status": "PENDING",
    }

    # monkeypatch api_request to handle POST and GET
    def fake_api_request(method, url, client=None, headers=None, json=None):
        if method == "POST" and url == "/api/inbox/":
            return {"success": True, "data": created_item, "error": None}
        if method == "GET" and url == "/api/inbox/":
            return {"success": True, "data": [created_item], "error": None}
        return {"success": False, "data": None, "error": "unexpected"}

    monkeypatch.setattr(auth_utils, "_api_request", lambda *a, **k: fake_api_request(*a, **k))

    module = _import_page()
    # enable auto fetch and call render to trigger fetch + submit handling
    fake_st.session_state["auto_fetch"] = True
    module._render()

    # success message present
    assert any("Item added" in s for s in fake_st.successes)
    # inputs cleared
    assert fake_st.session_state.get("inbox_content", "") == ""
    assert fake_st.session_state.get("inbox_priority") == 3
    # displayed list includes created item
    # either via dataframe or writes
    shown = False
    for df in fake_st.dataframes:
        if any(r.get("content") == "Test quick capture" for r in df):
            shown = True
    for w in fake_st.writes:
        if "Test quick capture" in (w or ""):
            shown = True
    assert shown


def test_empty_content_shows_error_and_no_api_call(fake_st, monkeypatch):
    fake_st.session_state["is_authenticated"] = True
    fake_st.session_state["access_token"] = "tok"
    fake_st.session_state["auto_fetch"] = False

    fake_st._inputs["Content"] = "   "
    from fs_flowstate_svc.schemas.inbox_schemas import InboxCategory
    fake_st._inputs["Category"] = InboxCategory.TODO
    fake_st._inputs["Priority"] = 3
    fake_st._form_submits["inbox_form"] = True

    called = {"count": 0}

    def fake_api_request(method, url, client=None, headers=None, json=None):
        called["count"] += 1
        return {"success": False, "data": None, "error": "should not be called"}

    monkeypatch.setattr(auth_utils, "_api_request", lambda *a, **k: fake_api_request(*a, **k))

    module = _import_page()
    module._render()

    # error shown
    assert any("Content cannot be empty" in e for e in fake_st.errors)
    # api not called
    assert called["count"] == 0
