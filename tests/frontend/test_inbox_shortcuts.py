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

    def set_page_config(self, **kwargs):
        pass

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


def _import_module(name: str):
    if name in sys.modules:
        del sys.modules[name]
    return importlib.import_module(name)


def test_edit_shortcut_sets_editing_id(fake_st):
    fake_st.session_state.clear()
    fake_st.session_state["is_authenticated"] = True
    # seed cache
    fake_st.session_state["inbox_items_cache"] = [{"id": "itm-1", "content": "one"}]
    fake_st.session_state["inbox_selected_item_idx"] = 0
    # simulate pressing E
    fake_st.session_state["inbox_last_key"] = "E"
    fake_st.session_state["inbox_last_key_shift"] = False

    mod = _import_module("fs_flowstate_svc.frontend.pages.inbox_keyboard")
    mod.handle_inbox_shortcut(fake_st)

    assert fake_st.session_state.get("inbox_editing_id") == "itm-1"
    assert fake_st.session_state.get("inbox_focus_edit_content") is True


def test_delete_confirm_triggers_delete_and_refetch(fake_st, monkeypatch):
    fake_st.session_state.clear()
    fake_st.session_state["is_authenticated"] = True
    fake_st.session_state["inbox_items_cache"] = [{"id": "itm-del", "content": "del"}]
    fake_st.session_state["inbox_selected_item_idx"] = 0
    # press D
    fake_st.session_state["inbox_last_key"] = "D"
    fake_st.session_state["inbox_last_key_shift"] = False

    calls = {"deleted": None, "fetched": False}

    def fake_api_request(method, url, client=None, headers=None, json=None):
        calls["deleted"] = {"method": method, "url": url, "json": json}
        return {"success": True, "data": None, "error": None}

    monkeypatch.setattr(auth_utils, "_api_request", lambda *a, **k: fake_api_request(*a, **k))

    def fake_fetch(st):
        calls["fetched"] = True

    monkeypatch.setattr("fs_flowstate_svc.frontend.pages.inbox_filters.fetch_items_with_filters", fake_fetch)

    mod = _import_module("fs_flowstate_svc.frontend.pages.inbox_keyboard")
    mod.handle_inbox_shortcut(fake_st)

    # confirm prompt shown
    assert fake_st.session_state.get("inbox_show_delete_confirm") is True
    assert fake_st.session_state.get("inbox_pending_delete_id") == "itm-del"

    # simulate user confirming delete
    mod.confirm_delete(fake_st, confirm=True)

    assert calls["deleted"] is not None
    assert calls["deleted"]["method"] == "DELETE"
    assert "/api/inbox/itm-del" in calls["deleted"]["url"]
    assert calls["fetched"] is True
    # flags cleared
    assert fake_st.session_state.get("inbox_show_delete_confirm") is False
    assert fake_st.session_state.get("inbox_pending_delete_id") is None


def test_archive_priority_and_category_shortcuts_trigger_updates_and_refetch(fake_st, monkeypatch):
    fake_st.session_state.clear()
    fake_st.session_state["is_authenticated"] = True
    fake_st.session_state["inbox_items_cache"] = [{"id": "itm-arc", "content": "arc"}]
    fake_st.session_state["inbox_selected_item_idx"] = 0

    calls = {"last": None, "refetch": 0}

    def fake_api_request(method, url, client=None, headers=None, json=None):
        calls["last"] = {"method": method, "url": url, "json": json}
        return {"success": True, "data": None, "error": None}

    def fake_fetch(st):
        calls["refetch"] += 1

    monkeypatch.setattr(auth_utils, "_api_request", lambda *a, **k: fake_api_request(*a, **k))
    monkeypatch.setattr("fs_flowstate_svc.frontend.pages.inbox_filters.fetch_items_with_filters", fake_fetch)

    mod = _import_module("fs_flowstate_svc.frontend.pages.inbox_keyboard")

    # Archive (A)
    fake_st.session_state["inbox_last_key"] = "A"
    fake_st.session_state["inbox_last_key_shift"] = False
    mod.handle_inbox_shortcut(fake_st)
    assert calls["last"]["method"] == "POST"
    assert "/api/inbox/bulk/archive" in calls["last"]["url"]
    assert calls["refetch"] == 1

    # Priority (2)
    fake_st.session_state["inbox_last_key"] = "2"
    fake_st.session_state["inbox_last_key_shift"] = False
    mod.handle_inbox_shortcut(fake_st)
    assert calls["last"]["method"] == "PUT"
    assert "/api/inbox/itm-arc" in calls["last"]["url"]
    assert calls["last"]["json"]["priority"] == 2
    assert calls["refetch"] == 2

    # Category T
    fake_st.session_state["inbox_last_key"] = "T"
    fake_st.session_state["inbox_last_key_shift"] = False
    mod.handle_inbox_shortcut(fake_st)
    assert calls["last"]["method"] == "PUT"
    assert calls["last"]["json"]["category"] == "TODO"
    assert calls["refetch"] == 3


def test_toggle_selection_and_shift_select_clear(fake_st):
    fake_st.session_state.clear()
    fake_st.session_state["inbox_items_cache"] = [
        {"id": "a", "content": "a"},
        {"id": "b", "content": "b"},
    ]
    fake_st.session_state["inbox_selected_item_idx"] = 1

    mod = _import_module("fs_flowstate_svc.frontend.pages.inbox_keyboard")

    # toggle X -> add b
    fake_st.session_state["inbox_last_key"] = "X"
    fake_st.session_state["inbox_last_key_shift"] = False
    mod.handle_inbox_shortcut(fake_st)
    assert fake_st.session_state.get("inbox_selected_ids") == ["b"]

    # toggle X again -> remove b
    fake_st.session_state["inbox_last_key"] = "X"
    fake_st.session_state["inbox_last_key_shift"] = False
    mod.handle_inbox_shortcut(fake_st)
    assert fake_st.session_state.get("inbox_selected_ids") == []

    # Shift+A select all
    fake_st.session_state["inbox_last_key"] = "A"
    fake_st.session_state["inbox_last_key_shift"] = True
    mod.handle_inbox_shortcut(fake_st)
    assert set(fake_st.session_state.get("inbox_selected_ids", [])) == {"a", "b"}
    assert fake_st.session_state.get("inbox_select_all") is True

    # Shift+C clear
    fake_st.session_state["inbox_last_key"] = "C"
    fake_st.session_state["inbox_last_key_shift"] = True
    mod.handle_inbox_shortcut(fake_st)
    assert fake_st.session_state.get("inbox_selected_ids") == []
    assert fake_st.session_state.get("inbox_select_all") is False


def test_no_selected_item_no_api_calls(fake_st, monkeypatch):
    fake_st.session_state.clear()
    fake_st.session_state["inbox_items_cache"] = []
    fake_st.session_state["inbox_selected_item_idx"] = None

    called = {"count": 0}

    def fake_api_request(*a, **k):
        called["count"] += 1
        return {"success": False}

    monkeypatch.setattr(auth_utils, "_api_request", lambda *a, **k: fake_api_request(*a, **k))

    mod = _import_module("fs_flowstate_svc.frontend.pages.inbox_keyboard")
    fake_st.session_state["inbox_last_key"] = "A"
    fake_st.session_state["inbox_last_key_shift"] = False
    mod.handle_inbox_shortcut(fake_st)

    assert called["count"] == 0
