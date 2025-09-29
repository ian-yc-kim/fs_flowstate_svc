import importlib
import sys

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


def _import_page():
    module_name = "fs_flowstate_svc.frontend.pages.inbox_page"
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


def test_shift_slash_toggles_overlay(fake_st):
    fake_st.session_state.clear()
    fake_st.session_state["is_authenticated"] = True

    # simulate pressing Shift + /
    fake_st.session_state["inbox_last_key"] = "/"
    fake_st.session_state["inbox_last_key_shift"] = True

    mod = _import_page()

    # overlay should open
    assert fake_st.session_state.get("show_shortcuts_help") is True or fake_st.session_state.get("inbox_show_help_overlay") is True

    # press Shift + / again to close
    fake_st.session_state["inbox_last_key"] = "/"
    fake_st.session_state["inbox_last_key_shift"] = True
    mod._render()
    assert fake_st.session_state.get("show_shortcuts_help") is False


def test_overlay_displays_all_shortcuts(fake_st):
    fake_st.session_state.clear()
    fake_st.session_state["is_authenticated"] = True

    mod = _import_page()
    # directly set overlay visible and render
    fake_st.session_state["show_shortcuts_help"] = True
    mod._render()

    # gather markdown outputs
    combined = "\n".join([m or "" for m in fake_st.markdowns])

    expected_keys = [
        "N: Create New Item",
        "J: Next Item",
        "K: Previous Item",
        "/: Focus Filters",
        "E: Edit Selected Item",
        "D: Delete Selected Item",
        "A: Archive Selected Item",
        "1-5: Set Priority",
        "T: Set Category (TODO)",
        "I: Set Category (IDEA)",
        "O: Set Category (NOTE)",
        "X: Toggle Selection",
        "Shift+A: Select All Visible Items",
        "Shift+C: Clear All Selections",
        "Shift+/: Toggle Shortcut Help",
        "Esc: Dismiss Help",
    ]

    for k in expected_keys:
        assert k in combined


def test_escape_dismisses_overlay(fake_st):
    fake_st.session_state.clear()
    fake_st.session_state["is_authenticated"] = True

    mod = _import_page()
    # open overlay
    fake_st.session_state["show_shortcuts_help"] = True

    # press Escape
    fake_st.session_state["inbox_last_key"] = "ESC"
    fake_st.session_state["inbox_last_key_shift"] = False
    mod._render()

    assert fake_st.session_state.get("show_shortcuts_help") is False
