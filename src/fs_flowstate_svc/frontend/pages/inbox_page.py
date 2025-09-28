import logging
import asyncio
import inspect
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlencode

import streamlit as st

from fs_flowstate_svc.frontend import auth_utils
from fs_flowstate_svc.schemas.inbox_schemas import (
    InboxItemCreate,
    InboxCategory,
    InboxPriority,
    InboxStatus,
)

logger = logging.getLogger(__name__)


def _safe_run_coro(maybe_awaitable):
    """Safely run an awaitable or return a non-awaitable result.

    Tests sometimes monkeypatch auth_utils._api_request with a synchronous
    function returning a dict. This helper supports both awaitables (coroutines)
    and plain values.
    """
    try:
        # If it's awaitable (coroutine or awaitable object), run it
        if inspect.isawaitable(maybe_awaitable):
            try:
                return asyncio.run(maybe_awaitable)
            except RuntimeError:
                # Running inside an existing loop; create a new loop to execute
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(maybe_awaitable)
                finally:
                    try:
                        loop.close()
                    except Exception:
                        pass
        # Non-awaitable: return as-is (useful for sync mocks in tests)
        return maybe_awaitable
    except Exception as e:
        logger.error(e, exc_info=True)
        return None


def _ensure_session_state_defaults():
    st.session_state.setdefault("inbox_content", "")
    st.session_state.setdefault("inbox_category", InboxCategory.TODO)
    st.session_state.setdefault("inbox_priority", 3)
    st.session_state.setdefault("inbox_items_cache", [])
    # Filters
    st.session_state.setdefault("inbox_filters", {
        "category": None,
        "status": None,
        "priority_min": None,
        "priority_max": None,
    })
    # remember last-applied filters to avoid redundant fetches
    st.session_state.setdefault("inbox_filters_applied", None)
    # Selection and bulk/edit state
    st.session_state.setdefault("inbox_selected_ids", [])
    st.session_state.setdefault("inbox_select_all", False)
    st.session_state.setdefault("inbox_editing_id", None)


def _build_query_from_filters(filters: Dict[str, Optional[Any]]) -> str:
    params: Dict[str, Any] = {}
    if filters.get("category") is not None:
        # Enum -> value
        params["category"] = filters["category"].value if hasattr(filters["category"], "value") else filters["category"]
    if filters.get("status") is not None:
        params["status"] = filters["status"].value if hasattr(filters["status"], "value") else filters["status"]
    if filters.get("priority_min") is not None:
        params["priority_min"] = filters["priority_min"] if isinstance(filters["priority_min"], int) else getattr(filters["priority_min"], "value", filters.get("priority_min"))
    if filters.get("priority_max") is not None:
        params["priority_max"] = filters["priority_max"] if isinstance(filters["priority_max"], int) else getattr(filters["priority_max"], "value", filters.get("priority_max"))
    if not params:
        return ""
    return "?" + urlencode(params)


def _fetch_items_with_filters(use_session_filters: bool = True) -> None:
    try:
        filters = st.session_state.get("inbox_filters", {}) if use_session_filters else {}
        query = _build_query_from_filters(filters)
        url = f"/api/inbox/{query}"
        result = _safe_run_coro(
            auth_utils._api_request("GET", url, headers=auth_utils.get_auth_headers())
        )
        if result and result.get("success"):
            data = result.get("data") or []
            st.session_state["inbox_items_cache"] = data
        else:
            if result is not None and result.get("error"):
                st.error(result.get("error"))
    except Exception as e:
        logger.error(e, exc_info=True)
        st.error("Failed fetching inbox items")


def _render():
    try:
        st.set_page_config(page_title="Inbox")

        _ensure_session_state_defaults()

        # If not logged in, prompt
        if not auth_utils.is_logged_in():
            st.markdown("<p>Please log in to view your inbox.</p>", unsafe_allow_html=True)
            return

        # Quick capture form (keep existing behavior)
        try:
            with st.form("inbox_form"):
                content = st.text_input("Content")
                category = st.selectbox("Category", [c for c in InboxCategory], index=0)
                priority = st.slider("Priority", min_value=1, max_value=5, value=3)
                submitted = st.form_submit_button("Add Item")

                if submitted:
                    # simple validation
                    if not content or not content.strip():
                        st.error("Content cannot be empty")
                    else:
                        # build payload using schema
                        try:
                            payload = InboxItemCreate(
                                content=content.strip(),
                                category=category if isinstance(category, InboxCategory) else InboxCategory(category),
                                priority=InboxPriority(priority),
                                status=InboxStatus.PENDING,
                            ).model_dump()
                        except Exception as e:
                            logger.error(e, exc_info=True)
                            st.error("Failed building request payload")
                        else:
                            try:
                                result = _safe_run_coro(
                                    auth_utils._api_request("POST", "/api/inbox/", headers=auth_utils.get_auth_headers(), json=payload)
                                )
                                if result and result.get("success"):
                                    created = result.get("data") or {}
                                    # optimistic update: append to cache
                                    cache: List[Dict[str, Any]] = st.session_state.get("inbox_items_cache", [])
                                    try:
                                        cache.insert(0, created)
                                        st.session_state["inbox_items_cache"] = cache
                                    except Exception:
                                        logger.error("Failed optimistic update", exc_info=True)
                                    # clear inputs
                                    st.session_state["inbox_content"] = ""
                                    st.session_state["inbox_category"] = InboxCategory.TODO
                                    st.session_state["inbox_priority"] = 3
                                    st.success("Item added")
                                else:
                                    err = (result or {}).get("error") if isinstance(result, dict) else "Unknown error"
                                    st.error(err or "Failed creating inbox item")
                            except Exception as e:
                                logger.error(e, exc_info=True)
                                st.error("An error occurred while creating inbox item.")

        except Exception as e:
            logger.error(e, exc_info=True)
            st.error("Unexpected error rendering form")

        # Filtering UI
        try:
            # read current filters from session_state to prefill
            sess_filters = st.session_state.get("inbox_filters", {})
            # Category filter
            category_options = [None] + [c for c in InboxCategory]
            sel_category = st.selectbox("Filter Category", category_options, index=0)
            # Status filter
            status_options = [None] + [s for s in InboxStatus]
            sel_status = st.selectbox("Filter Status", status_options, index=0)
            # Priority min/max
            pr_min = st.selectbox("Priority Min", [None, 1, 2, 3, 4, 5], index=0)
            pr_max = st.selectbox("Priority Max", [None, 1, 2, 3, 4, 5], index=0)

            # Update session filters
            st.session_state["inbox_filters"] = {
                "category": sel_category,
                "status": sel_status,
                "priority_min": pr_min,
                "priority_max": pr_max,
            }

            # Apply filters immediately only when auto_fetch enabled and filters changed
            if st.session_state.get("auto_fetch", True):
                applied = st.session_state.get("inbox_filters_applied")
                current = st.session_state.get("inbox_filters")
                # only fetch when filters differ from last applied
                if applied != current:
                    _fetch_items_with_filters()
                    # store a shallow copy as applied
                    try:
                        st.session_state["inbox_filters_applied"] = dict(current)
                    except Exception:
                        st.session_state["inbox_filters_applied"] = current

        except Exception as e:
            logger.error(e, exc_info=True)
            st.error("Failed rendering filters")

        # Bulk operations UI
        try:
            # Select All checkbox (visible UI element)
            try:
                # prefer native checkbox where available
                sel_all_val = st.session_state.get("inbox_select_all", False)
                sel_all = st.checkbox("Select All", key="inbox_select_all", value=sel_all_val)
                # sync session state in case checkbox returned a value
                st.session_state["inbox_select_all"] = bool(sel_all)
            except Exception:
                # fallback: leave session_state as-is
                pass

            with st.form("bulk_form"):
                bulk_action = st.selectbox("Bulk Action", ["", "Mark as Done", "Mark as Pending", "Archive Selected"], index=0)
                bulk_submit = st.form_submit_button("Apply")

                if bulk_submit:
                    try:
                        # Determine selected ids
                        items = st.session_state.get("inbox_items_cache", []) or []
                        selected: List[str] = []
                        if st.session_state.get("inbox_select_all"):
                            selected = [it.get("id") for it in items]
                        else:
                            # read per-item selection keys from session_state
                            for it in items:
                                key = f"select_{it.get('id')}"
                                if st.session_state.get(key):
                                    selected.append(it.get("id"))

                        if not selected:
                            st.error("No items selected for bulk operation")
                        else:
                            if bulk_action == "Mark as Done":
                                payload = {"item_ids": selected, "new_status": "DONE"}
                                res = _safe_run_coro(auth_utils._api_request("POST", "/api/inbox/bulk/status", headers=auth_utils.get_auth_headers(), json=payload))
                            elif bulk_action == "Mark as Pending":
                                payload = {"item_ids": selected, "new_status": "PENDING"}
                                res = _safe_run_coro(auth_utils._api_request("POST", "/api/inbox/bulk/status", headers=auth_utils.get_auth_headers(), json=payload))
                            elif bulk_action == "Archive Selected":
                                payload = {"item_ids": selected}
                                res = _safe_run_coro(auth_utils._api_request("POST", "/api/inbox/bulk/archive", headers=auth_utils.get_auth_headers(), json=payload))
                            else:
                                st.error("Unknown bulk action")
                                res = None

                            if res and res.get("success"):
                                # clear selection state
                                st.session_state["inbox_selected_ids"] = []
                                st.session_state["inbox_select_all"] = False
                                # also clear per-item keys
                                for itid in selected:
                                    try:
                                        if f"select_{itid}" in st.session_state:
                                            st.session_state.pop(f"select_{itid}", None)
                                    except Exception:
                                        pass
                                # refresh list
                                _fetch_items_with_filters()
                                st.success(res.get("data") or res.get("message") or "Bulk operation successful")
                            else:
                                err = (res or {}).get("error") if isinstance(res, dict) else "Bulk operation failed"
                                st.error(err or "Bulk operation failed")

                    except Exception as e:
                        logger.error(e, exc_info=True)
                        st.error("Bulk operation failed")
        except Exception as e:
            logger.error(e, exc_info=True)
            st.error("Failed rendering bulk operations")

        # Fetch items (ensure at least once if not fetched by filters)
        try:
            if st.session_state.get("auto_fetch", True) and not st.session_state.get("inbox_items_cache"):
                _fetch_items_with_filters()
        except Exception as e:
            logger.error(e, exc_info=True)

        # Display items
        try:
            items = st.session_state.get("inbox_items_cache", []) or []
            if not items:
                st.write("No inbox items yet.")
            else:
                # Attempt to render as dataframe for convenience
                try:
                    import pandas as _pd  # type: ignore

                    rows = []
                    for it in items:
                        rows.append({
                            "id": it.get("id"),
                            "content": it.get("content"),
                            "category": it.get("category"),
                            "priority": it.get("priority"),
                            "status": it.get("status"),
                        })
                    df = _pd.DataFrame(rows)
                    st.dataframe(df)
                except Exception:
                    for it in items:
                        st.write(f"- {it.get('content')} | {it.get('category')} | priority: {it.get('priority')} | status: {it.get('status')}")

                # Visual indicators and per-item checkbox + edit button
                priority_icons = {1: "🔥", 2: "🔶", 3: "⭐", 4: "🔹", 5: "⚪"}
                status_icons = {
                    "PENDING": "🕒",
                    "SCHEDULED": "📅",
                    "ARCHIVED": "📦",
                    "DONE": "✅",
                }

                for it in items:
                    try:
                        iid = it.get("id")
                        pr = int(it.get("priority", 3)) if it.get("priority") is not None else 3
                        p_icon = priority_icons.get(pr, str(pr))
                        s_icon = status_icons.get(it.get("status"), it.get("status"))
                        label = f"{s_icon} {p_icon} {it.get('content')} | {it.get('category')} | priority: {it.get('priority')} | status: {it.get('status')}"

                        # Checkbox for selection
                        try:
                            checked = st.checkbox(label, key=f"select_{iid}", value=bool(st.session_state.get(f"select_{iid}", False)))
                            st.session_state[f"select_{iid}"] = bool(checked)
                        except Exception:
                            # fallback: rely on session_state
                            pass

                        # Edit button
                        try:
                            pressed = st.button("Edit", key=f"edit_{iid}")
                            if pressed:
                                st.session_state["inbox_editing_id"] = iid
                        except Exception:
                            # fallback: no-op if button unavailable
                            pass

                    except Exception as e:
                        logger.error(e, exc_info=True)

                # Per-item edit UI (driven by session_state editing id)
                edit_id = st.session_state.get("inbox_editing_id")
                if edit_id:
                    # find item
                    item_to_edit = None
                    for it in items:
                        if str(it.get("id")) == str(edit_id):
                            item_to_edit = it
                            break

                    if item_to_edit is not None:
                        try:
                            form_name = f"edit_form_{edit_id}"
                            with st.form(form_name):
                                content_key = f"Edit Content - {edit_id}"
                                category_key = f"Edit Category - {edit_id}"
                                priority_key = f"Edit Priority - {edit_id}"
                                status_key = f"Edit Status - {edit_id}"
                                action_key = f"Edit Action - {edit_id}"

                                new_content = st.text_input(content_key)
                                new_category = st.selectbox(category_key, [c for c in InboxCategory], index=0)
                                new_priority = st.slider(priority_key, min_value=1, max_value=5, value=item_to_edit.get("priority", 3))
                                new_status = st.selectbox(status_key, [s for s in InboxStatus], index=0)
                                action_choice = st.selectbox(action_key, ["Save", "Cancel"], index=0)

                                submitted = st.form_submit_button("Apply")

                                if submitted:
                                    if action_choice == "Cancel":
                                        st.session_state["inbox_editing_id"] = None
                                    else:
                                        # Build partial payload comparing to existing
                                        payload: Dict[str, Any] = {}
                                        if new_content is not None and new_content.strip() != item_to_edit.get("content"):
                                            if not new_content.strip():
                                                st.error("Content cannot be empty")
                                            else:
                                                payload["content"] = new_content.strip()
                                        if new_category is not None and (new_category.value if hasattr(new_category, "value") else new_category) != item_to_edit.get("category"):
                                            payload["category"] = new_category.value if hasattr(new_category, "value") else new_category
                                        if new_priority is not None and int(new_priority) != int(item_to_edit.get("priority")):
                                            payload["priority"] = int(new_priority)
                                        if new_status is not None and (new_status.value if hasattr(new_status, "value") else new_status) != item_to_edit.get("status"):
                                            payload["status"] = new_status.value if hasattr(new_status, "value") else new_status

                                        if not payload:
                                            st.error("No changes to save")
                                        else:
                                            try:
                                                put_url = f"/api/inbox/{edit_id}"
                                                res = _safe_run_coro(auth_utils._api_request("PUT", put_url, headers=auth_utils.get_auth_headers(), json=payload))
                                                if res and res.get("success"):
                                                    updated = res.get("data") or {}
                                                    # update cache in-place
                                                    try:
                                                        for idx, it in enumerate(st.session_state.get("inbox_items_cache", [])):
                                                            if str(it.get("id")) == str(edit_id):
                                                                st.session_state["inbox_items_cache"][idx] = updated
                                                                break
                                                    except Exception:
                                                        logger.error("Failed updating cache after edit", exc_info=True)

                                                    st.session_state["inbox_editing_id"] = None
                                                    st.success("Item updated")
                                                else:
                                                    err = (res or {}).get("error") if isinstance(res, dict) else "Failed updating item"
                                                    st.error(err or "Failed updating item")
                                            except Exception as e:
                                                logger.error(e, exc_info=True)
                                                st.error("Error while updating item")
                        except Exception as e:
                            logger.error(e, exc_info=True)
                            st.error("Failed rendering edit UI")
                    else:
                        st.error("Item to edit not found")

        except Exception as e:
            logger.error(e, exc_info=True)
            st.error("Failed rendering inbox items")

    except Exception as e:
        logger.error(e, exc_info=True)
        try:
            st.error("Unexpected error rendering inbox page.")
        except Exception:
            pass


# render on import to mimic Streamlit behavior
_render()
