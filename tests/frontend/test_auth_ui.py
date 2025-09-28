import importlib
import sys
from types import SimpleNamespace

import pytest

from fs_flowstate_svc.frontend import auth_utils


class FakeStreamlit:
    def __init__(self):
        # simulate Streamlit session state
        self.session_state = {}
        # inputs keyed by label
        self._inputs = {}
        # form submits keyed by form name
        self._form_submits = {}
        # button returns keyed by label
        self._buttons = {}
        self.set_page_config_called = False
        self.errors = []
        self.successes = []
        self.switch_page_calls = []
        self._current_form = None

    def set_page_config(self, **kwargs):
        self.set_page_config_called = True

    # context manager for form
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

    def text_input(self, label, type=None):
        # Return value seeded by tests
        return self._inputs.get(label, "")

    def form_submit_button(self, label):
        # Determine current form
        return bool(self._form_submits.get(self._current_form, False))

    def button(self, label):
        return bool(self._buttons.get(label, False))

    def error(self, msg):
        self.errors.append(msg)

    def success(self, msg):
        self.successes.append(msg)

    def switch_page(self, name):
        self.switch_page_calls.append(name)


@pytest.fixture(autouse=True)
def fake_st(monkeypatch):
    fake = FakeStreamlit()
    # inject fake streamlit module
    sys.modules["streamlit"] = fake
    # ensure auth_utils uses the same session_state object
    auth_utils.st = fake
    yield fake
    # cleanup
    auth_utils.st = getattr(auth_utils, "st", {})
    try:
        del sys.modules["streamlit"]
    except Exception:
        pass


def _import_page(module_name):
    # ensure module re-imported fresh
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


def test_login_success_redirects_home(fake_st, monkeypatch):
    # seed inputs
    fake_st._inputs["Username or Email"] = "user1"
    fake_st._inputs["Password"] = "password123"
    fake_st._form_submits["login_form"] = True

    async def fake_login(u, p):
        # simulate setting session state as auth_utils.login would
        auth_utils.st.session_state["access_token"] = "tok"
        auth_utils.st.session_state["is_authenticated"] = True
        return {"success": True, "data": {"access_token": "tok"}, "error": None}

    monkeypatch.setattr(auth_utils, "login", fake_login)

    # import page (renders on import)
    _import_page("fs_flowstate_svc.frontend.pages.login_page")

    assert "Home" in fake_st.switch_page_calls
    assert any("Login successful" in s or "Login successful." in s for s in fake_st.successes)


def test_login_failure_shows_error(fake_st, monkeypatch):
    fake_st._inputs["Username or Email"] = "user1"
    fake_st._inputs["Password"] = "wrong"
    fake_st._form_submits["login_form"] = True

    async def fake_login(u, p):
        return {"success": False, "data": None, "error": "Invalid credentials"}

    monkeypatch.setattr(auth_utils, "login", fake_login)

    _import_page("fs_flowstate_svc.frontend.pages.login_page")

    assert "Home" not in fake_st.switch_page_calls
    assert any("Invalid credentials" in e for e in fake_st.errors)


def test_register_success_redirects_login(fake_st, monkeypatch):
    fake_st._inputs["Username"] = "newuser"
    fake_st._inputs["Email"] = "newuser@example.com"
    fake_st._inputs["Password"] = "password123"
    fake_st._form_submits["register_form"] = True

    async def fake_register(u, e, p):
        return {"success": True, "data": {"username": u, "email": e}, "error": None}

    monkeypatch.setattr(auth_utils, "register", fake_register)

    _import_page("fs_flowstate_svc.frontend.pages.register_page")

    assert "Login" in fake_st.switch_page_calls
    assert any("Registration successful" in s or "Registration successful." in s for s in fake_st.successes)


def test_register_failure_shows_error(fake_st, monkeypatch):
    fake_st._inputs["Username"] = "newuser"
    fake_st._inputs["Email"] = "newuser@example.com"
    fake_st._inputs["Password"] = "password123"
    fake_st._form_submits["register_form"] = True

    async def fake_register(u, e, p):
        return {"success": False, "data": None, "error": "Email already exists"}

    monkeypatch.setattr(auth_utils, "register", fake_register)

    _import_page("fs_flowstate_svc.frontend.pages.register_page")

    assert "Login" not in fake_st.switch_page_calls
    assert any("Email already exists" in e for e in fake_st.errors)


def test_register_email_validation_blocks_api_call(fake_st, monkeypatch):
    fake_st._inputs["Username"] = "newuser"
    fake_st._inputs["Email"] = "not-an-email"
    fake_st._inputs["Password"] = "password123"
    fake_st._form_submits["register_form"] = True

    called = {"count": 0}

    async def fake_register(u, e, p):
        called["count"] += 1
        return {"success": True, "data": None, "error": None}

    monkeypatch.setattr(auth_utils, "register", fake_register)

    _import_page("fs_flowstate_svc.frontend.pages.register_page")

    # API should not be called due to email validation
    assert called["count"] == 0
    assert any("valid email" in (e.lower()) for e in fake_st.errors)


def test_navigation_buttons_switch_pages(fake_st):
    # From login page -> Register button
    fake_st._inputs["Username or Email"] = ""
    fake_st._inputs["Password"] = ""
    fake_st._form_submits["login_form"] = False
    fake_st._buttons["Register"] = True

    _import_page("fs_flowstate_svc.frontend.pages.login_page")
    assert "Register" in fake_st.switch_page_calls

    # From register page -> Login button
    fake_st._inputs.clear()
    fake_st._form_submits.clear()
    fake_st._buttons.clear()
    fake_st._buttons["Login"] = True

    _import_page("fs_flowstate_svc.frontend.pages.register_page")
    assert "Login" in fake_st.switch_page_calls
