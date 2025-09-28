import logging
from types import SimpleNamespace
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# Lightweight streamlit shim when streamlit is not available (for tests)
try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover - shim used during tests/environments without streamlit
    class _SessionState(dict):
        """Simple dict-like session_state shim."""
        pass

    st = SimpleNamespace(session_state=_SessionState())


async def _api_request(
    method: str,
    url: str,
    client: Optional[httpx.AsyncClient] = None,
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Internal helper to perform async http requests with structured result."""
    close_client = False
    if client is None:
        client = httpx.AsyncClient(base_url="http://localhost:8000")
        close_client = True

    try:
        resp = await client.request(method, url, headers=headers, json=json)
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            data = None
        return {"success": True, "data": data, "error": None}
    except httpx.HTTPStatusError as e:
        # Try to extract json detail
        error_text = None
        try:
            err_json = e.response.json()
            if isinstance(err_json, dict) and "detail" in err_json:
                error_text = err_json["detail"]
            else:
                error_text = str(err_json)
        except Exception:
            error_text = e.response.text or str(e)
        logger.error(e, exc_info=True)
        return {"success": False, "data": None, "error": error_text}
    except Exception as e:
        logger.error(e, exc_info=True)
        return {"success": False, "data": None, "error": str(e)}
    finally:
        if close_client:
            await client.aclose()


def get_auth_headers() -> Dict[str, str]:
    """Return Authorization headers if access_token present in session_state."""
    token = st.session_state.get("access_token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def is_logged_in() -> bool:
    """Check if user is marked authenticated in session_state and token exists."""
    return bool(st.session_state.get("is_authenticated") and st.session_state.get("access_token"))


def logout() -> None:
    """Clear authentication-related session_state keys."""
    for k in ("access_token", "token_type", "user_id", "username", "email"):
        if k in st.session_state:
            try:
                del st.session_state[k]
            except Exception:
                st.session_state.pop(k, None)
    st.session_state["is_authenticated"] = False


async def register(
    username: str,
    email: str,
    password: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Register a new user via /users/register endpoint."""
    payload = {"username": username, "email": email, "password": password}
    try:
        return await _api_request("POST", "/users/register", client=client, json=payload)
    except Exception as e:
        logger.error(e, exc_info=True)
        return {"success": False, "data": None, "error": str(e)}


async def login(
    username_or_email: str,
    password: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Login user via /users/login endpoint and populate session_state on success."""
    payload = {"username_or_email": username_or_email, "password": password}
    try:
        result = await _api_request("POST", "/users/login", client=client, json=payload)
        if not result.get("success"):
            # Ensure no leftover session
            logout()
            return result

        token_data = result.get("data") or {}
        access_token = token_data.get("access_token")
        token_type = token_data.get("token_type", "bearer")
        if not access_token:
            logout()
            return {"success": False, "data": None, "error": "Missing access token in response"}

        # Store token in session
        st.session_state["access_token"] = access_token
        st.session_state["token_type"] = token_type
        st.session_state["is_authenticated"] = True

        # Fetch user profile
        profile = await get_current_user_info(client=client)
        if not profile.get("success"):
            # Cleanup on failure
            logout()
            return {"success": False, "data": None, "error": profile.get("error")}

        return {"success": True, "data": token_data, "error": None}
    except Exception as e:
        logger.error(e, exc_info=True)
        logout()
        return {"success": False, "data": None, "error": str(e)}


async def get_current_user_info(client: Optional[httpx.AsyncClient] = None) -> Dict[str, Any]:
    """Get current user info from /users/me and sync session_state."""
    headers = get_auth_headers()
    if not headers:
        return {"success": False, "data": None, "error": "No authentication token present"}
    try:
        result = await _api_request("GET", "/users/me", client=client, headers=headers)
        if result.get("success") and result.get("data"):
            data = result["data"]
            # sync session
            st.session_state["user_id"] = data.get("id")
            st.session_state["username"] = data.get("username")
            st.session_state["email"] = data.get("email")
        return result
    except Exception as e:
        logger.error(e, exc_info=True)
        return {"success": False, "data": None, "error": str(e)}


async def update_profile(
    username: Optional[str] = None,
    email: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Update current user profile via PUT /users/me with partial data."""
    headers = get_auth_headers()
    if not headers:
        return {"success": False, "data": None, "error": "No authentication token present"}

    payload: Dict[str, Any] = {}
    if username is not None:
        payload["username"] = username
    if email is not None:
        payload["email"] = email

    try:
        result = await _api_request("PUT", "/users/me", client=client, headers=headers, json=payload)
        if result.get("success") and result.get("data"):
            data = result["data"]
            # update session state
            if "username" in data and data["username"]:
                st.session_state["username"] = data.get("username")
            if "email" in data and data["email"]:
                st.session_state["email"] = data.get("email")
        return result
    except Exception as e:
        logger.error(e, exc_info=True)
        return {"success": False, "data": None, "error": str(e)}
