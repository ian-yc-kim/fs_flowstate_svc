import logging
from typing import Any, List, Optional

from fs_flowstate_svc.frontend import auth_utils
from fs_flowstate_svc.frontend.pages import inbox_filters
from fs_flowstate_svc.frontend import keyboard_utils

logger = logging.getLogger(__name__)


def _get_selected_id(st: Any) -> Optional[str]:
    try:
        idx = st.session_state.get("inbox_selected_item_idx")
        cache = st.session_state.get("inbox_items_cache", []) or []
        if idx is None:
            return None
        # allow numeric strings
        try:
            i = int(idx)
        except Exception:
            return None
        if not isinstance(cache, list):
            return None
        if i < 0 or i >= len(cache):
            return None
        it = cache[i]
        if isinstance(it, dict):
            return it.get("id")
        return None
    except Exception as e:
        logger.error(e, exc_info=True)
        return None


def handle_inbox_shortcut(st: Any) -> None:
    """Main entrypoint to handle an inbox keyboard event stored in session_state.

    This function is test-friendly: it reads st.session_state keys set by tests and
    performs synchronous _api_request calls (the test harness typically monkeypatches
    auth_utils._api_request to a sync callable).
    """
    try:
        keyboard_utils.ensure_keyboard_listener(st)
        key, shift = keyboard_utils.read_and_clear_last_key(st)
        if not key:
            return
        key = str(key).upper()

        # Shift modified commands
        if shift and key == "A":
            _select_all_visible(st)
            return
        if shift and key == "C":
            _clear_selection(st)
            return

        # find selected id
        selected_id = _get_selected_id(st)

        # Edit
        if key == "E":
            if selected_id:
                st.session_state["inbox_editing_id"] = selected_id
                # UI code can use this to focus input
                st.session_state["inbox_focus_edit_content"] = True
            return

        # Delete (prompt)
        if key == "D":
            if selected_id:
                st.session_state["inbox_pending_delete_id"] = selected_id
                st.session_state["inbox_show_delete_confirm"] = True
            return

        # Archive
        if key == "A":
            if selected_id:
                _archive_items(st, [selected_id])
            return

        # Priority assignments 1-5
        if key in {"1", "2", "3", "4", "5"}:
            if selected_id:
                try:
                    payload = {"priority": int(key)}
                    headers = auth_utils.get_auth_headers()
                    resp = auth_utils._api_request("PUT", f"/api/inbox/{selected_id}", headers=headers, json=payload)
                except Exception as e:
                    logger.error(e, exc_info=True)
                    resp = {"success": False}
                if resp and isinstance(resp, dict) and resp.get("success"):
                    try:
                        inbox_filters.fetch_items_with_filters(st)
                    except Exception:
                        logger.error("fetch after priority update failed", exc_info=True)
            return

        # Categories T/I/O
        if key in {"T", "I", "O"}:
            if selected_id:
                mapping = {"T": "TODO", "I": "IDEA", "O": "NOTE"}
                cat = mapping.get(key)
                try:
                    payload = {"category": cat}
                    headers = auth_utils.get_auth_headers()
                    resp = auth_utils._api_request("PUT", f"/api/inbox/{selected_id}", headers=headers, json=payload)
                except Exception as e:
                    logger.error(e, exc_info=True)
                    resp = {"success": False}
                if resp and isinstance(resp, dict) and resp.get("success"):
                    try:
                        inbox_filters.fetch_items_with_filters(st)
                    except Exception:
                        logger.error("fetch after category update failed", exc_info=True)
            return

        # Toggle selection of highlighted item
        if key == "X":
            if selected_id:
                try:
                    sel = st.session_state.get("inbox_selected_ids", []) or []
                    if selected_id in sel:
                        sel = [s for s in sel if s != selected_id]
                    else:
                        sel = sel + [selected_id]
                    st.session_state["inbox_selected_ids"] = sel
                except Exception as e:
                    logger.error(e, exc_info=True)
            return

    except Exception as e:
        logger.error(e, exc_info=True)


def _archive_items(st: Any, ids: List[str]) -> None:
    try:
        payload = {"item_ids": ids}
        headers = auth_utils.get_auth_headers()
        resp = auth_utils._api_request("POST", "/api/inbox/bulk/archive", headers=headers, json=payload)
    except Exception as e:
        logger.error(e, exc_info=True)
        resp = {"success": False}
    if resp and isinstance(resp, dict) and resp.get("success"):
        try:
            inbox_filters.fetch_items_with_filters(st)
        except Exception:
            logger.error("fetch after archive failed", exc_info=True)


def _select_all_visible(st: Any) -> None:
    try:
        cache = st.session_state.get("inbox_items_cache", []) or []
        if isinstance(cache, list):
            ids = [it.get("id") for it in cache if isinstance(it, dict) and it.get("id")]
            st.session_state["inbox_selected_ids"] = ids
            st.session_state["inbox_select_all"] = True
    except Exception as e:
        logger.error(e, exc_info=True)


def _clear_selection(st: Any) -> None:
    try:
        st.session_state["inbox_selected_ids"] = []
        st.session_state["inbox_select_all"] = False
    except Exception as e:
        logger.error(e, exc_info=True)


def confirm_delete(st: Any, confirm: bool) -> None:
    """Perform pending delete when user confirms via UI.

    Tests can call this helper to simulate confirm/cancel.
    """
    try:
        pid = st.session_state.get("inbox_pending_delete_id")
        if not pid:
            st.session_state["inbox_show_delete_confirm"] = False
            return
        if confirm:
            try:
                headers = auth_utils.get_auth_headers()
                resp = auth_utils._api_request("DELETE", f"/api/inbox/{pid}", headers=headers)
            except Exception as e:
                logger.error(e, exc_info=True)
                resp = {"success": False}
            if resp and isinstance(resp, dict) and resp.get("success"):
                try:
                    inbox_filters.fetch_items_with_filters(st)
                except Exception:
                    logger.error("fetch after delete failed", exc_info=True)
        # clear pending flags
        try:
            st.session_state["inbox_pending_delete_id"] = None
            st.session_state["inbox_show_delete_confirm"] = False
        except Exception:
            pass
    except Exception as e:
        logger.error(e, exc_info=True)
