import logging
from typing import Any, Dict, List, Optional

from fs_flowstate_svc.frontend import auth_utils
from fs_flowstate_svc.schemas import inbox_schemas

logger = logging.getLogger(__name__)


def _serialize_enum_list(values: Optional[List[Any]]) -> Optional[str]:
    if not values:
        return None
    parts: List[str] = []
    for v in values:
        try:
            # Enum members may have .name or .value
            if hasattr(v, "name"):
                parts.append(str(v.name))
            elif hasattr(v, "value"):
                parts.append(str(v.value))
            else:
                parts.append(str(v))
        except Exception:
            try:
                parts.append(str(v))
            except Exception:
                continue
    return ",".join(parts) if parts else None


def ensure_session_state_defaults(st: Any) -> None:
    """Ensure inbox_filters and inbox_filters_applied exist in session_state."""
    try:
        if "inbox_filters" not in st.session_state:
            st.session_state["inbox_filters"] = {
                "categories": None,
                "statuses": None,
                "priorities": None,
                "priority_min": None,
                "priority_max": None,
                "filter_logic": "AND",
            }
        # Track what was applied to avoid unnecessary refetches
        if "inbox_filters_applied" not in st.session_state:
            st.session_state["inbox_filters_applied"] = None
    except Exception as e:
        logger.error(e, exc_info=True)


def build_query_from_filters(filters: Dict[str, Optional[Any]]) -> str:
    """Build a URL query string from a filters mapping.

    Expected keys: categories (list of InboxCategory), statuses (list of InboxStatus),
    priorities (list of InboxPriority or ints), priority_min, priority_max, filter_logic.

    If priorities list is present, priority_min and priority_max are ignored.
    """
    try:
        params: List[str] = []

        # categories
        cats = filters.get("categories")
        cat_csv = None
        try:
            if isinstance(cats, list):
                cat_csv = _serialize_enum_list(cats)
            elif cats is not None:
                cat_csv = str(cats)
        except Exception:
            cat_csv = None
        if cat_csv:
            params.append(f"categories={cat_csv}")

        # statuses
        sts = filters.get("statuses")
        sts_csv = None
        try:
            if isinstance(sts, list):
                sts_csv = _serialize_enum_list(sts)
            elif sts is not None:
                sts_csv = str(sts)
        except Exception:
            sts_csv = None
        if sts_csv:
            params.append(f"statuses={sts_csv}")

        # priorities list (takes precedence over min/max)
        pris = filters.get("priorities")
        pris_csv = None
        try:
            if isinstance(pris, list):
                # convert to int values if enums
                converted: List[str] = []
                for v in pris:
                    try:
                        if hasattr(v, "value"):
                            converted.append(str(int(v.value)))
                        else:
                            converted.append(str(int(v)))
                    except Exception:
                        # fallback to name or str
                        try:
                            if hasattr(v, "name"):
                                converted.append(str(v.name))
                            else:
                                converted.append(str(v))
                        except Exception:
                            continue
                if converted:
                    pris_csv = ",".join(converted)
            elif pris is not None:
                # single value
                if hasattr(pris, "value"):
                    pris_csv = str(int(pris.value))
                else:
                    try:
                        pris_csv = str(int(pris))
                    except Exception:
                        pris_csv = str(pris)
        except Exception:
            pris_csv = None
        if pris_csv:
            params.append(f"priorities={pris_csv}")
        else:
            # include min/max only when priorities not present
            pmin = filters.get("priority_min")
            pmax = filters.get("priority_max")
            try:
                if pmin is not None:
                    params.append(f"priority_min={int(pmin)}")
            except Exception:
                pass
            try:
                if pmax is not None:
                    params.append(f"priority_max={int(pmax)}")
            except Exception:
                pass

        # filter_logic: only include when other filters present to maintain backward compatibility
        logic = filters.get("filter_logic")
        try:
            if logic is not None and params:
                s = str(logic).strip().upper()
                if s == "OR":
                    params.append("filter_logic=OR")
                else:
                    params.append("filter_logic=AND")
        except Exception:
            if params:
                params.append("filter_logic=AND")

        if not params:
            return ""
        return "?" + "&".join(params)
    except Exception as e:
        logger.error(e, exc_info=True)
        return ""


def clear_filters(st: Any) -> None:
    """Reset inbox_filters to defaults and mark applied as None to force refetch."""
    try:
        st.session_state["inbox_filters"] = {
            "categories": None,
            "statuses": None,
            "priorities": None,
            "priority_min": None,
            "priority_max": None,
            "filter_logic": "AND",
        }
        st.session_state["inbox_filters_applied"] = None
    except Exception as e:
        logger.error(e, exc_info=True)


def fetch_items_with_filters(st: Any) -> Optional[Dict[str, Any]]:
    """Call the backend inbox list endpoint using current session inbox_filters.

    Stores results into st.session_state["inbox_items_cache"] when successful.
    Returns the API response dict or None on failure.
    """
    try:
        filters = st.session_state.get("inbox_filters", {})
        q = build_query_from_filters(filters or {})
        url = "/api/inbox/"
        if q:
            url = f"{url}{q}"

        headers = {}
        try:
            headers = auth_utils.get_auth_headers()
        except Exception:
            headers = {}

        resp = None
        try:
            resp = auth_utils._api_request("GET", url, headers=headers)
        except Exception as e:
            logger.error(e, exc_info=True)
            return None

        if resp and isinstance(resp, dict) and resp.get("success"):
            try:
                st.session_state["inbox_items_cache"] = resp.get("data", [])
            except Exception:
                logger.error("Failed storing inbox_items_cache", exc_info=True)
        return resp
    except Exception as e:
        logger.error(e, exc_info=True)
        return None
