import asyncio
import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from fs_flowstate_svc.app import app
from fs_flowstate_svc.frontend import auth_utils


@pytest.fixture(autouse=True)
def clear_session_state(client):
    # Ensure session_state is clear before each test and activate DB overrides via client fixture
    auth_utils.st.session_state.clear()
    yield
    auth_utils.st.session_state.clear()


@pytest.mark.asyncio
async def test_register_success(client):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client_async:
        username = f"user_{uuid.uuid4().hex[:8]}"
        email = f"{username}@example.com"
        res = await auth_utils.register(username, email, "password123", client=client_async)
        assert res["success"] is True
        assert res["data"] is not None
        assert res["data"].get("username") == username
        assert res["data"].get("email") == email


@pytest.mark.asyncio
async def test_login_success_and_headers(client):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client_async:
        username = f"user_{uuid.uuid4().hex[:8]}"
        email = f"{username}@example.com"
        password = "password123"
        reg = await auth_utils.register(username, email, password, client=client_async)
        assert reg["success"]

        res = await auth_utils.login(username, password, client=client_async)
        assert res["success"] is True
        # session_state set
        assert auth_utils.is_logged_in()
        assert "access_token" in auth_utils.st.session_state
        headers = auth_utils.get_auth_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")


@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client_async:
        username = f"user_{uuid.uuid4().hex[:8]}"
        email = f"{username}@example.com"
        password = "password123"
        reg = await auth_utils.register(username, email, password, client=client_async)
        assert reg["success"]

        res = await auth_utils.login(username, "wrongpassword", client=client_async)
        assert res["success"] is False
        assert res["error"] is not None
        assert not auth_utils.is_logged_in()


@pytest.mark.asyncio
async def test_logout_clears_state(client):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client_async:
        username = f"user_{uuid.uuid4().hex[:8]}"
        email = f"{username}@example.com"
        password = "password123"
        await auth_utils.register(username, email, password, client=client_async)
        await auth_utils.login(username, password, client=client_async)
        assert auth_utils.is_logged_in()
        auth_utils.logout()
        assert not auth_utils.is_logged_in()
        assert "access_token" not in auth_utils.st.session_state


@pytest.mark.asyncio
async def test_get_current_user_info_success(client):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client_async:
        username = f"user_{uuid.uuid4().hex[:8]}"
        email = f"{username}@example.com"
        password = "password123"
        await auth_utils.register(username, email, password, client=client_async)
        await auth_utils.login(username, password, client=client_async)

        res = await auth_utils.get_current_user_info(client=client_async)
        assert res["success"] is True
        assert res["data"]["username"] == username
        assert auth_utils.st.session_state.get("username") == username


@pytest.mark.asyncio
async def test_get_current_user_info_no_token(client):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client_async:
        # ensure no token
        auth_utils.logout()
        res = await auth_utils.get_current_user_info(client=client_async)
        assert res["success"] is False
        assert res["error"] is not None


@pytest.mark.asyncio
async def test_update_profile_username_and_conflict_email(client):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client_async:
        # create two users
        username1 = f"user_{uuid.uuid4().hex[:8]}"
        email1 = f"{username1}@example.com"
        password = "password123"
        await auth_utils.register(username1, email1, password, client=client_async)

        username2 = f"user_{uuid.uuid4().hex[:8]}"
        email2 = f"{username2}@example.com"
        await auth_utils.register(username2, email2, password, client=client_async)

        # login as user1
        await auth_utils.login(username1, password, client=client_async)
        new_username = username1 + "_new"
        res = await auth_utils.update_profile(username=new_username, client=client_async)
        assert res["success"] is True
        assert auth_utils.st.session_state.get("username") == new_username

        # attempt to update email to email2 -> conflict expected
        res_conflict = await auth_utils.update_profile(email=email2, client=client_async)
        assert res_conflict["success"] is False
        assert res_conflict["error"] is not None


def test_get_auth_headers_missing_token():
    auth_utils.logout()
    headers = auth_utils.get_auth_headers()
    assert headers == {}
