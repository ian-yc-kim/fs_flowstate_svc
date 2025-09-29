# Inbox API - Advanced Filtering

This document describes the GET /api/inbox/ endpoint's advanced filtering capabilities.

Overview

- Endpoint: GET /api/inbox/
- Authentication: Required (Bearer Token)
- Purpose: Retrieve a user's inbox items with powerful filter options supporting multi-select and flexible logic.

New filtering fields (InboxItemFilter)

- categories: optional, multi-select. Accepts a list of InboxCategory values (CSV in query string or repeated query params). Items matching any category in the list will match this filter.
  - Enum values: TODO, IDEA, NOTE
  - Query examples:
    - ?categories=TODO,IDEA
    - ?categories=TODO&categories=IDEA

- statuses: optional, multi-select. Accepts a list of InboxStatus values (CSV or repeated param). Items matching any status in the list will match this filter.
  - Enum values: PENDING, SCHEDULED, ARCHIVED, DONE
  - Query examples:
    - ?statuses=PENDING,ARCHIVED
    - ?statuses=PENDING&statuses=DONE

- priorities: optional, multi-select. Accepts a list of InboxPriority values (CSV or repeated param). Numeric values (1-5) or enum names are accepted.
  - Enum values (integer): P1=1, P2=2, P3=3, P4=4, P5=5
  - Query examples:
    - ?priorities=1,2
    - ?priorities=P1,P2

- priority_min / priority_max: optional. When priorities list is not provided, you may filter by a numeric range.
  - Query example: ?priority_min=2&priority_max=4

- filter_logic: optional. Controls how different filter types are combined (categories, statuses, priorities, priority_min/max).
  - Allowed values: AND (default), OR
  - Behavior:
    - AND: an item must satisfy all provided filter types to be included (e.g., category in categories AND status in statuses AND priority criteria)
    - OR: an item that matches any single filter clause will be included (e.g., category match OR status match OR priority match)
  - Query examples:
    - ?categories=TODO&statuses=PENDING&filter_logic=AND
    - ?categories=TODO&statuses=PENDING&filter_logic=OR

Notes about multi-select parsing

- Query string CSV: the API accepts comma-separated lists in a single query parameter (e.g., categories=TODO,IDEA).
- Repeated query parameters are also supported by client libraries (e.g., ?categories=TODO&categories=IDEA).
- Priorities accept either integer values (1..5) or enum names (P1..P5). Numeric values are parsed into enum values.
- Legacy singular params are still accepted for backward compatibility: category, status, priority. These are normalized to the multi-select equivalents by the server.

Examples

1) AND logic (default) — items that are TODO and PENDING

GET /api/inbox/?categories=TODO&statuses=PENDING

2) OR logic — items that are TODO or PENDING

GET /api/inbox/?categories=TODO&statuses=PENDING&filter_logic=OR

3) Multi-select categories and numeric priorities

GET /api/inbox/?categories=TODO,IDEA&priorities=1,2

4) Priority range (min/max)

GET /api/inbox/?priority_min=2&priority_max=4

Schema summary (InboxItemFilter)

- categories: optional List[InboxCategory]
- statuses: optional List[InboxStatus]
- priorities: optional List[InboxPriority]
- priority_min: optional InboxPriority
- priority_max: optional InboxPriority
- filter_logic: optional str ("AND" | "OR") default "AND"

Enums

- InboxCategory: TODO, IDEA, NOTE
- InboxStatus: PENDING, SCHEDULED, ARCHIVED, DONE
- InboxPriority: P1=1, P2=2, P3=3, P4=4, P5=5

Response

- The endpoint returns a list of InboxItemResponse objects ordered newest-first (created_at desc). Pagination via skip and limit applies.

Implementation notes for clients

- When building URLs from UI components that provide arrays (e.g., multiselect widgets), either serialize as CSV or repeat the query parameter for compatibility across HTTP clients.
- Keep tokens out of logs and prefer Authorization: Bearer <token> header for REST calls.

Compatibility

- The server accepts legacy singular parameters for backward compatibility and normalizes them to the multi-select equivalents.
- This advanced filtering is additive and does not change existing endpoints' semantics when no filter fields are provided.
