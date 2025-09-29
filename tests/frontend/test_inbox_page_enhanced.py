import importlib
import sys
from types import SimpleNamespace

import pytest

from fs_flowstate_svc.frontend import auth_utils


class FakeStreamlit:
    def __init__(self):
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
        self.dataframes.append(df.to_dict(orient="records"))

    def error(self, msg):
        self.errors.append(msg)

    def success(self, msg):
        self.successes.append(msg)

    def checkbox(self, label, value=False, key=None):
        if key is not None:
            return self._inputs.get(key, self.session_state.get(key, value))
        return self._inputs.get(label, value)

    def button(self, label, key=None):
        if key is not None:
            return bool(self._inputs.get(key, False)) or bool(self._form_submits.get(key, False))
        return bool(self._inputs.get(label, False))


@pytest.fixture(autouse=True)
def fake_st(monkeypatch):
    fake = FakeStreamlit()
    sys.modules["streamlit"] = fake
    auth_utils.st = fake
    yield fake
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

    from fs_flowstate_svc.schemas.inbox_schemas import InboxCategory, InboxStatus

    # set multi-select style inputs
    fake_st._inputs["Filter Categories"] = [InboxCategory.TODO]
    fake_st._inputs["Filter Statuses"] = [InboxStatus.PENDING]
    fake_st._inputs["Priority Min"] = 1
    fake_st._inputs["Priority Max"] = 3

    calls = {"last": None}

    def fake_api_request(method, url, client=None, headers=None, json=None):
        calls["last"] = {"method": method, "url": url, "json": json}
        if method == "GET":
            return {"success": True, "data": [], "error": None}
        return {"success": False, "data": None, "error": "unexpected"}

    monkeypatch.setattr(auth_utils, "_api_request", lambda *a, **k: fake_api_request(*a, **k))

    module = _import_page()
    module._render()

    assert calls["last"] is not None
    assert calls["last"]["method"] == "GET"
    assert "categories=TODO" in calls["last"]["url"]
    assert "statuses=PENDING" in calls["last"]["url"]
    assert "priority_min=1" in calls["last"]["url"]
    assert "priority_max=3" in calls["last"]["url"]


def test_multiselect_filters_and_filter_logic(fake_st, monkeypatch):
    fake_st.session_state["is_authenticated"] = True
    fake_st.session_state["access_token"] = "tok"
    from fs_flowstate_svc.schemas.inbox_schemas import InboxCategory, InboxStatus, InboxPriority

    fake_st._inputs["Filter Categories"] = [InboxCategory.TODO, InboxCategory.IDEA]
    fake_st._inputs["Filter Statuses"] = [InboxStatus.PENDING]
    fake_st._inputs["Filter Priorities"] = [InboxPriority.P1, InboxPriority.P3]
    fake_st._inputs["Filter Logic"] = "OR"

    captured = {"called": False, "url": None}

    def fake_api_request(method, url, headers=None, json=None, client=None):
        captured["called"] = True
        captured["url"] = url
        return {"success": True, "data": [], "error": None}

    monkeypatch.setattr(auth_utils, "_api_request", lambda *a, **k: fake_api_request(*a, **k))

    module = _import_page()
    module._render()

    assert captured["called"]
    assert "categories=TODO,IDEA" in captured["url"]
    assert "statuses=PENDING" in captured["url"]
    assert "priorities=1,3" in captured["url"]
    assert "filter_logic=OR" in captured["url"]


def test_clear_filters_button_triggers_refetch(fake_st, monkeypatch):
    fake_st.session_state["is_authenticated"] = True
    fake_st.session_state["access_token"] = "tok"

    from fs_flowstate_svc.schemas.inbox_schemas import InboxCategory

    # initial filters set
    fake_st._inputs["Filter Categories"] = [InboxCategory.NOTE]

    calls = {"history": []}

    def fake_api_request(method, url, headers=None, json=None, client=None):
        calls["history"].append({"method": method, "url": url})
        return {"success": True, "data": [], "error": None}

    monkeypatch.setattr(auth_utils, "_api_request", lambda *a, **k: fake_api_request(*a, **k))

    # first render to apply filters and populate applied
    module = _import_page()
    module._render()

    # now simulate Clear Filters button press
    fake_st._inputs["clear_filters_btn"] = True
    module._render()

    # last GET should be without categories query
    get_calls = [c for c in calls["history"] if c["method"] == "GET"]
    assert get_calls
    # last GET's URL should not contain categories=
    last_url = get_calls[-1]["url"]
    assert "categories=" not in last_url
    # session filters reset
    assert fake_st.session_state["inbox_filters"]["categories"] is None
