import pytest

from fs_flowstate_svc.frontend import keyboard_utils, auth_utils
from fs_flowstate_svc.frontend.pages import inbox_page


class FakeSt:
    def __init__(self):
        self.session_state = {}
        self._inputs = {}
        self.markdowns = []

    def markdown(self, s: str) -> None:
        # capture markdown output for assertions
        self.markdowns.append(s)


def test_ensure_keyboard_listener_sets_keys():
    st = FakeSt()
    keyboard_utils.ensure_keyboard_listener(st, "inbox")
    assert "inbox_last_key" in st.session_state
    assert "inbox_last_key_shift" in st.session_state


def test_read_and_clear_last_key_behavior():
    st = FakeSt()
    st.session_state["inbox_last_key"] = "ENTER"
    st.session_state["inbox_last_key_shift"] = True
    key, shift = keyboard_utils.read_and_clear_last_key(st, "inbox")
    assert key == "ENTER"
    assert shift is True
    # ensure values were cleared (best-effort semantics)
    assert st.session_state.get("inbox_last_key") in (None,)
    assert st.session_state.get("inbox_last_key_shift") in (False,)


def test_read_and_clear_handles_missing_keys_gracefully():
    st = FakeSt()
    # No keys set should not raise and should return (None, False)
    key, shift = keyboard_utils.read_and_clear_last_key(st, "inbox")
    assert key is None
    assert shift is False


def test_inbox_page_shows_login_when_not_authenticated(monkeypatch):
    st = FakeSt()
    st.session_state["is_authenticated"] = False
    # Patch the shared st used by frontend pages
    monkeypatch.setattr(auth_utils, "st", st)

    # Call the render entrypoint and verify the login prompt was emitted
    inbox_page._render()
    assert any("Please log in" in m for m in st.markdowns)
