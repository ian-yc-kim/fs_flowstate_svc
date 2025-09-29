import logging
from typing import Any, Dict, List, Optional

from fs_flowstate_svc.frontend import auth_utils, keyboard_utils
from fs_flowstate_svc.frontend.pages import inbox_filters
from fs_flowstate_svc.schemas import inbox_schemas

logger = logging.getLogger(__name__)


def _ensure_session_state_defaults(st: Any) -> None:
    try:
        # Ensure standardized overlay flag early so keyboard listener toggles
        # it even if inbox_filters.ensure_session_state_defaults raises.
        st.session_state.setdefault("show_shortcuts_help", False)
        # legacy key preserved for backward compat
        st.session_state.setdefault("inbox_show_help_overlay", st.session_state.get("show_shortcuts_help", False))

        inbox_filters.ensure_session_state_defaults(st)
        if "inbox_items_cache" not in st.session_state:
            st.session_state["inbox_items_cache"] = []
        if "auto_fetch" not in st.session_state:
            st.session_state["auto_fetch"] = True
        st.session_state.setdefault("inbox_focus_registry", [])
        st.session_state.setdefault("inbox_focus_index", 0)
        st.session_state.setdefault("inbox_focus_target", None)
        st.session_state.setdefault("inbox_create_active", False)
        st.session_state.setdefault("inbox_return_focus", None)
    except Exception as e:
        logger.error(e, exc_info=True)


def _apply_ui_filters_to_session(st: Any) -> None:
    try:
        cats = None
        try:
            cats = st._inputs.get("Filter Categories", st._inputs.get("Filter Category", None))
        except Exception:
            cats = None
        sts = None
        try:
            sts = st._inputs.get("Filter Statuses", st._inputs.get("Filter Status", None))
        except Exception:
            sts = None
        pris = None
        try:
            pris = st._inputs.get("Filter Priorities", None)
        except Exception:
            pris = None
        pmin = st._inputs.get("Priority Min", None)
        pmax = st._inputs.get("Priority Max", None)
        logic = st._inputs.get("Filter Logic", None)

        f = st.session_state.get("inbox_filters", {}) or {}
        f["categories"] = cats if cats is not None else None
        f["statuses"] = sts if sts is not None else None
        f["priorities"] = pris if pris is not None else None
        try:
            if pris:
                f["priority_min"] = None
                f["priority_max"] = None
            else:
                f["priority_min"] = int(pmin) if pmin is not None else None
                f["priority_max"] = int(pmax) if pmax is not None else None
        except Exception:
            f["priority_min"] = None
            f["priority_max"] = None
        try:
            f["filter_logic"] = str(logic).upper() if logic is not None else f.get("filter_logic", "AND")
        except Exception:
            f["filter_logic"] = f.get("filter_logic", "AND")
        st.session_state["inbox_filters"] = f
    except Exception as e:
        logger.error(e, exc_info=True)


def _render_filter_widgets(st: Any) -> None:
    try:
        f = st.session_state.get("inbox_filters", {}) or {}
        default_cats = f.get("categories")
        default_statuses = f.get("statuses")
        default_pris = f.get("priorities")
        default_logic = f.get("filter_logic", "AND")

        try:
            cats = st.multiselect("Filter Categories", options=list(inbox_schemas.InboxCategory), default=default_cats)
        except Exception:
            cats = st._inputs.get("Filter Categories", default_cats)
        try:
            st._inputs["Filter Categories"] = cats
        except Exception:
            pass

        try:
            statuses = st.multiselect("Filter Statuses", options=list(inbox_schemas.InboxStatus), default=default_statuses)
        except Exception:
            statuses = st._inputs.get("Filter Statuses", default_statuses)
        try:
            st._inputs["Filter Statuses"] = statuses
        except Exception:
            pass

        try:
            priority_opts = [p for p in inbox_schemas.InboxPriority]
            pris = st.multiselect("Filter Priorities", options=priority_opts, default=default_pris)
        except Exception:
            pris = st._inputs.get("Filter Priorities", default_pris)
        try:
            st._inputs["Filter Priorities"] = pris
        except Exception:
            pass

        try:
            pmin = st.number_input("Priority Min", value=default_pris[0].value if isinstance(default_pris, list) and default_pris else (f.get("priority_min") or 1))
        except Exception:
            pmin = st._inputs.get("Priority Min", f.get("priority_min"))
        try:
            st._inputs["Priority Min"] = pmin
        except Exception:
            pass
        try:
            pmax = st.number_input("Priority Max", value=default_pris[-1].value if isinstance(default_pris, list) and default_pris else (f.get("priority_max") or 5))
        except Exception:
            pmax = st._inputs.get("Priority Max", f.get("priority_max"))
        try:
            st._inputs["Priority Max"] = pmax
        except Exception:
            pass

        try:
            logic = st.selectbox("Filter Logic", ["AND", "OR"], index=0 if default_logic == "AND" else 1)
        except Exception:
            logic = st._inputs.get("Filter Logic", default_logic)
        try:
            st._inputs["Filter Logic"] = logic
        except Exception:
            pass

        try:
            pressed = st.button("Clear Filters", key="clear_filters_btn")
        except Exception:
            pressed = bool(st._inputs.get("clear_filters_btn", False))
        try:
            if pressed:
                st._inputs["clear_filters_btn"] = True
        except Exception:
            pass

    except Exception as e:
        logger.error(e, exc_info=True)


def _render_filters_ui(st: Any) -> None:
    try:
        try:
            clear_pressed = bool(st._inputs.get("clear_filters_btn", False))
        except Exception:
            clear_pressed = False
        if clear_pressed:
            try:
                inbox_filters.clear_filters(st)
                st.session_state["inbox_filters_applied"] = None
                inbox_filters.fetch_items_with_filters(st)
            except Exception as e:
                logger.error(e, exc_info=True)
    except Exception as e:
        logger.error(e, exc_info=True)


# Accessibility helpers
def _build_focus_registry(st: Any) -> List[str]:
    try:
        registry: List[str] = []
        registry.extend([
            "filter_categories",
            "filter_statuses",
            "filter_priorities",
            "priority_min",
            "priority_max",
            "filter_logic",
            "clear_filters_btn",
        ])
        registry.extend(["bulk_action_select", "bulk_apply_btn"])
        registry.extend(["create_content", "create_category", "create_priority", "create_add_btn"])
        registry.append("inbox_list")

        if st.session_state.get("inbox_editing_id"):
            eid = st.session_state.get("inbox_editing_id")
            registry = [f"edit_content_{eid}", f"edit_category_{eid}", f"edit_priority_{eid}", f"edit_status_{eid}", f"edit_save_{eid}", f"edit_cancel_{eid}"]
        elif st.session_state.get("inbox_create_active"):
            registry = ["create_content", "create_category", "create_priority", "create_add_btn", "create_cancel_btn"]
        elif st.session_state.get("show_shortcuts_help") or st.session_state.get("inbox_show_help_overlay"):
            # overlay present: focus close button
            registry = ["help_close_btn"]

        st.session_state["inbox_focus_registry"] = registry
        idx = st.session_state.get("inbox_focus_index", 0)
        if not isinstance(idx, int) or idx < 0:
            idx = 0
        if registry:
            st.session_state["inbox_focus_index"] = idx % len(registry)
        else:
            st.session_state["inbox_focus_index"] = 0
        return registry
    except Exception as e:
        logger.error(e, exc_info=True)
        return []


def _apply_keyboard_navigation(st: Any) -> None:
    try:
        key, shift = keyboard_utils.read_and_clear_last_key(st, "inbox")
        if not key:
            return
        key_norm = str(key).upper()

        registry = _build_focus_registry(st)
        total = len(registry)
        idx = int(st.session_state.get("inbox_focus_index", 0) or 0)

        # Toggle help overlay: Shift + /
        try:
            if shift and key_norm == "/":
                # store return focus and toggle
                st.session_state["inbox_return_focus"] = keyboard_utils.get_focus_target(st, "inbox") or (registry[idx] if registry else None)
                new_val = not bool(st.session_state.get("show_shortcuts_help", False))
                st.session_state["show_shortcuts_help"] = new_val
                # keep legacy key synced
                st.session_state["inbox_show_help_overlay"] = new_val
                if new_val:
                    keyboard_utils.set_focus_target(st, "inbox", "help_close_btn")
                else:
                    keyboard_utils.set_focus_target(st, "inbox", st.session_state.get("inbox_return_focus"))
                return
        except Exception as e:
            logger.error(e, exc_info=True)

        if key_norm in ("ESC", "ESCAPE"):
            try:
                # close help overlay
                if st.session_state.get("show_shortcuts_help") or st.session_state.get("inbox_show_help_overlay"):
                    st.session_state["show_shortcuts_help"] = False
                    st.session_state["inbox_show_help_overlay"] = False
                    keyboard_utils.set_focus_target(st, "inbox", st.session_state.get("inbox_return_focus"))
                    return
                if st.session_state.get("inbox_editing_id"):
                    st.session_state["inbox_editing_id"] = None
                    keyboard_utils.set_focus_target(st, "inbox", st.session_state.get("inbox_return_focus"))
                    return
                if st.session_state.get("inbox_create_active"):
                    st.session_state["inbox_create_active"] = False
                    keyboard_utils.set_focus_target(st, "inbox", st.session_state.get("inbox_return_focus"))
                    return
            except Exception as e:
                logger.error(e, exc_info=True)
            return

        if key_norm in ("ENTER", "\n"):
            try:
                sel_idx = st.session_state.get("inbox_selected_item_idx")
                if sel_idx is not None and st.session_state.get("inbox_editing_id") is None and not st.session_state.get("inbox_create_active") and not st.session_state.get("show_shortcuts_help") and not st.session_state.get("inbox_show_help_overlay"):
                    cache = st.session_state.get("inbox_items_cache", []) or []
                    if isinstance(cache, list) and 0 <= int(sel_idx) < len(cache):
                        item = cache[int(sel_idx)]
                        try:
                            item_id = item.get("id") if isinstance(item, dict) else None
                        except Exception:
                            item_id = None
                        if item_id is not None:
                            st.session_state["inbox_return_focus"] = keyboard_utils.get_focus_target(st, "inbox") or (registry[idx] if registry else None)
                            st.session_state["inbox_editing_id"] = item_id
                            keyboard_utils.set_focus_target(st, "inbox", f"edit_content_{item_id}")
            except Exception as e:
                logger.error(e, exc_info=True)
            return

        if key_norm in ("TAB",):
            try:
                if total == 0:
                    return
                new_idx = (idx - 1) % total if shift else (idx + 1) % total
                st.session_state["inbox_focus_index"] = new_idx
                new_target = registry[new_idx] if registry and 0 <= new_idx < len(registry) else None
                keyboard_utils.set_focus_target(st, "inbox", new_target)
            except Exception as e:
                logger.error(e, exc_info=True)
            return

    except Exception as e:
        logger.error(e, exc_info=True)


def _render_help_overlay(st: Any) -> None:
    try:
        if st.session_state.get("show_shortcuts_help") or st.session_state.get("inbox_show_help_overlay"):
            try:
                # Provide a clear listing of all implemented shortcuts
                content = "<div role=\"dialog\" aria-modal=\"true\" style=\"background:rgba(0,0,0,0.6);padding:20px;border-radius:8px;color:#fff;\">"
                content += "<h3>Keyboard Shortcuts</h3>"
                content += "<ul>"
                content += "<li>N: Create New Item</li>"
                content += "<li>J: Next Item</li>"
                content += "<li>K: Previous Item</li>"
                content += "<li>/: Focus Filters</li>"
                content += "<li>E: Edit Selected Item</li>"
                content += "<li>D: Delete Selected Item</li>"
                content += "<li>A: Archive Selected Item</li>"
                content += "<li>1-5: Set Priority (P1-P5) for Selected Item</li>"
                content += "<li>T: Set Category (TODO) for Selected Item</li>"
                content += "<li>I: Set Category (IDEA) for Selected Item</li>"
                content += "<li>O: Set Category (NOTE) for Selected Item</li>"
                content += "<li>X: Toggle Selection for Selected Item</li>"
                content += "<li>Shift+A: Select All Visible Items</li>"
                content += "<li>Shift+C: Clear All Selections</li>"
                content += "<li>Shift+/: Toggle Shortcut Help</li>"
                content += "<li>Esc: Dismiss Help</li>"
                content += "</ul>"
                content += "<button data-focus-id=\"help_close_btn\">Close</button>"
                content += "</div>"
                st.markdown(content, unsafe_allow_html=True)
            except Exception:
                st.markdown("Keyboard Shortcuts: N, J, K, /, E, D, A, 1-5, T, I, O, X, Shift+A, Shift+C, Shift+/ (Esc to close)")
    except Exception as e:
        logger.error(e, exc_info=True)


def _render_inbox_list_aria(st: Any) -> None:
    try:
        cache = st.session_state.get("inbox_items_cache", []) or []
        sel = st.session_state.get("inbox_selected_item_idx")
        parts: List[str] = ["<ul role=\"list\" aria-label=\"Inbox Items\">"]
        for i, it in enumerate(cache):
            try:
                content = it.get("content") if isinstance(it, dict) else str(it)
            except Exception:
                content = str(it)
            selected = "true" if sel is not None and int(sel) == i else "false"
            fid = f"inbox-item-idx-{i}"
            parts.append(f"<li role=\"listitem\" data-focus-id=\"{fid}\" aria-selected=\"{selected}\" tabindex=\"0\" aria-label=\"{content}\">{content}</li>")
        parts.append("</ul>")
        try:
            st.markdown("".join(parts), unsafe_allow_html=True)
        except Exception:
            for i, it in enumerate(cache):
                try:
                    st.markdown((it.get("content") if isinstance(it, dict) else str(it)))
                except Exception:
                    pass
    except Exception as e:
        logger.error(e, exc_info=True)


def _render() -> None:
    st = auth_utils.st
    try:
        try:
            keyboard_utils.ensure_keyboard_listener(st, "inbox")
        except Exception:
            pass
        _ensure_session_state_defaults(st)
    except Exception as e:
        logger.error(e, exc_info=True)

    try:
        if not bool(st.session_state.get("is_authenticated", False)):
            try:
                st.markdown("Please log in to access your inbox.")
            except Exception:
                logger.debug("failed to render login prompt", exc_info=True)
            return
    except Exception as e:
        try:
            st.markdown("Please log in to access your inbox.")
        except Exception:
            logger.debug("failed to render login prompt in fallback", exc_info=True)
        return

    try:
        _apply_keyboard_navigation(st)
    except Exception as e:
        logger.error(e, exc_info=True)

    try:
        _render_filter_widgets(st)
    except Exception as e:
        logger.error(e, exc_info=True)

    try:
        _apply_ui_filters_to_session(st)
    except Exception as e:
        logger.error(e, exc_info=True)

    try:
        _render_filters_ui(st)
    except Exception as e:
        logger.error(e, exc_info=True)

    try:
        with st.form("bulk_form"):
            try:
                action = st.selectbox("Bulk Action", ["Mark as Done", "Archive Selected"])
            except Exception:
                action = st._inputs.get("Bulk Action")
            submit_bulk = st.form_submit_button("Apply")
        if submit_bulk:
            try:
                selected_ids: List[str] = []
                if st.session_state.get("inbox_select_all", False):
                    cache = st.session_state.get("inbox_items_cache", []) or []
                    if isinstance(cache, list):
                        selected_ids = [it.get("id") for it in cache if isinstance(it, dict) and it.get("id")]
                else:
                    selected_ids = st.session_state.get("inbox_selected_ids", []) or []

                if selected_ids:
                    new_status = "DONE" if action == "Mark as Done" else "ARCHIVED"
                    payload = {"item_ids": selected_ids, "new_status": new_status}
                    headers = {}
                    try:
                        headers = auth_utils.get_auth_headers()
                    except Exception:
                        headers = {}
                    try:
                        resp = auth_utils._api_request("POST", "/api/inbox/bulk/status" if new_status == "DONE" else "/api/inbox/bulk/archive", headers=headers, json=payload)
                    except Exception as e:
                        logger.error(e, exc_info=True)
                        resp = {"success": False}
                    if resp and isinstance(resp, dict) and resp.get("success"):
                        try:
                            st.session_state["inbox_select_all"] = False
                        except Exception:
                            pass
                        try:
                            inbox_filters.fetch_items_with_filters(st)
                        except Exception:
                            logger.debug("fetch after bulk failed", exc_info=True)
                    else:
                        try:
                            st.error("Bulk action failed")
                        except Exception:
                            pass
            except Exception as e:
                logger.error(e, exc_info=True)
    except Exception as e:
        logger.error(e, exc_info=True)

    try:
        editing_id = st.session_state.get("inbox_editing_id")
        if editing_id:
            form_name = f"edit_form_{editing_id}"
            try:
                with st.form(form_name):
                    edit_content = st.text_input(f"Edit Content - {editing_id}")
                    edit_category = st.selectbox(f"Edit Category - {editing_id}", list(inbox_schemas.InboxCategory))
                    edit_priority = st.slider(f"Edit Priority - {editing_id}", 1, 5, 3)
                    edit_status = st.selectbox(f"Edit Status - {editing_id}", list(inbox_schemas.InboxStatus))
                    _ = st.selectbox(f"Edit Action - {editing_id}", ["Save", "Cancel"])
                    submitted = st.form_submit_button("Save")
                if submitted:
                    try:
                        payload: Dict[str, Any] = {}
                        if edit_content is not None:
                            payload["content"] = edit_content
                        if edit_category is not None:
                            payload["category"] = edit_category.name if hasattr(edit_category, "name") else str(edit_category)
                        if edit_priority is not None:
                            try:
                                payload["priority"] = int(edit_priority)
                            except Exception:
                                payload["priority"] = edit_priority
                        if edit_status is not None:
                            payload["status"] = edit_status.name if hasattr(edit_status, "name") else str(edit_status)

                        headers = {}
                        try:
                            headers = auth_utils.get_auth_headers()
                        except Exception:
                            headers = {}
                        try:
                            resp = auth_utils._api_request("PUT", f"/api/inbox/{editing_id}", headers=headers, json=payload)
                        except Exception as e:
                            logger.error(e, exc_info=True)
                            resp = {"success": False}

                        if resp and isinstance(resp, dict) and resp.get("success"):
                            try:
                                data = resp.get("data")
                                cache = st.session_state.get("inbox_items_cache") or []
                                if isinstance(cache, list) and data and isinstance(data, dict):
                                    for idx, it in enumerate(cache):
                                        if str(it.get("id")) == str(editing_id):
                                            cache[idx] = data
                                            break
                                    st.session_state["inbox_items_cache"] = cache
                            except Exception:
                                logger.error("Failed updating cache after edit", exc_info=True)
                            try:
                                st.session_state["_skip_fetch_once"] = True
                            except Exception:
                                pass
                            try:
                                st.session_state["inbox_editing_id"] = None
                            except Exception:
                                pass
                            return
                        else:
                            try:
                                st.error("Failed to save item")
                            except Exception:
                                pass
                    except Exception as e:
                        logger.error(e, exc_info=True)
            except Exception as e:
                logger.error(e, exc_info=True)
    except Exception as e:
        logger.error(e, exc_info=True)

    try:
        with st.form("inbox_form"):
            content = st.text_input("Content")
            category = st.selectbox("Category", list(inbox_schemas.InboxCategory))
            priority = st.slider("Priority", 1, 5, 3)
            submit = st.form_submit_button("Add")
        if submit:
            try:
                invalid = False
                try:
                    if content is None or str(content).strip() == "":
                        invalid = True
                        st.error("Content cannot be empty")
                except Exception:
                    invalid = True
                if not invalid:
                    payload = {"content": content}
                    try:
                        if category is not None:
                            payload["category"] = category.name if hasattr(category, "name") else str(category)
                    except Exception:
                        payload["category"] = str(category)
                    try:
                        payload["priority"] = int(priority)
                    except Exception:
                        try:
                            payload["priority"] = int(str(priority))
                        except Exception:
                            payload["priority"] = 3
                    headers = {}
                    try:
                        headers = auth_utils.get_auth_headers()
                    except Exception:
                        headers = {}
                    try:
                        resp = auth_utils._api_request("POST", "/api/inbox/", headers=headers, json=payload)
                    except Exception as e:
                        logger.error(e, exc_info=True)
                        resp = {"success": False}
                    try:
                        if resp and isinstance(resp, dict) and resp.get("success"):
                            try:
                                st.success("Item added")
                            except Exception:
                                pass
                            try:
                                st.session_state["inbox_content"] = ""
                                st.session_state["inbox_priority"] = 3
                            except Exception:
                                pass
                            try:
                                if st.session_state.get("auto_fetch", True):
                                    inbox_filters.fetch_items_with_filters(st)
                            except Exception:
                                logger.debug("auto fetch after create failed", exc_info=True)
                        else:
                            try:
                                st.error("Failed to add item")
                            except Exception:
                                pass
                    except Exception as e:
                        logger.error(e, exc_info=True)
            except Exception as e:
                logger.error(e, exc_info=True)
    except Exception as e:
        logger.error(e, exc_info=True)

    try:
        skip = False
        try:
            skip = bool(st.session_state.pop("_skip_fetch_once", False))
        except Exception:
            skip = False
        try:
            applied = st.session_state.get("inbox_filters_applied")
            current = st.session_state.get("inbox_filters")
            if current is None:
                current = {}

            def _norm(x):
                if isinstance(x, dict):
                    out = {}
                    for k, v in x.items():
                        if isinstance(v, list):
                            out[k] = tuple([getattr(i, "name", getattr(i, "value", i)) for i in v])
                        else:
                            out[k] = v
                    return out
                return x

            try:
                if not skip and (applied is None or _norm(applied) != _norm(current)):
                    if st.session_state.get("auto_fetch", True):
                        inbox_filters.fetch_items_with_filters(st)
                        try:
                            st.session_state["inbox_filters_applied"] = current.copy() if isinstance(current, dict) else current
                        except Exception:
                            st.session_state["inbox_filters_applied"] = current
            except Exception as e:
                logger.error(e, exc_info=True)
        except Exception as e:
            logger.error(e, exc_info=True)
    except Exception as e:
        logger.error(e, exc_info=True)

    try:
        cache = st.session_state.get("inbox_items_cache", []) or []
        if isinstance(cache, list) and cache:
            try:
                import pandas as _pd
                try:
                    st.dataframe(_pd.DataFrame(cache))
                except Exception:
                    for it in cache:
                        try:
                            st.write(it.get("content") if isinstance(it, dict) else str(it))
                        except Exception:
                            logger.error("failed writing inbox item", exc_info=True)
            except Exception:
                for it in cache:
                    try:
                        st.write(it.get("content") if isinstance(it, dict) else str(it))
                    except Exception:
                        logger.error("failed writing inbox item", exc_info=True)

        try:
            _render_inbox_list_aria(st)
        except Exception as e:
            logger.error(e, exc_info=True)
    except Exception as e:
        logger.error(e, exc_info=True)


try:
    _render()
except Exception:
    logger.debug("inbox_page import-time render suppressed", exc_info=True)
