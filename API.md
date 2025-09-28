# API Documentation

This document provides detailed information about the API endpoints available in the FlowState service.

## Authentication

The following endpoints handle user authentication, registration, and password management.

### Register User

**Endpoint:** `POST /users/register`

**Description:** Registers a new user with a unique username and email.

**Request Body:** `UserCreate` schema
```json
{
  "username": "string",
  "email": "string",
  "password": "string"
}
```

**Response:** `UserResponse` schema
```json
{
  "id": "uuid",
  "username": "string",
  "email": "string"
}
```

**Authentication:** None

**Status Codes:**
- `200 OK`: User registered successfully
- `409 Conflict`: Username or email already exists
- `422 Unprocessable Entity`: Invalid request data
- `500 Internal Server Error`: Server error

---

### Login

**Endpoint:** `POST /users/login`

**Description:** Authenticates a user and returns a JWT access token.

**Request Body:** `UserLogin` schema
```json
{
  "username_or_email": "string",
  "password": "string"
}
```

**Response:** `Token` schema
```json
{
  "access_token": "string",
  "token_type": "bearer"
}
```

**Authentication:** None

**Status Codes:**
- `200 OK`: Login successful
- `401 Unauthorized`: Incorrect username or password
- `500 Internal Server Error`: Server error

---

### Get Current User

**Endpoint:** `GET /users/me`

**Description:** Retrieves the details of the currently authenticated user.

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Response:** `UserResponse` schema
```json
{
  "id": "uuid",
  "username": "string",
  "email": "string"
}
```

**Authentication:** Required (Bearer Token)

**Status Codes:**
- `200 OK`: User details retrieved successfully
- `401 Unauthorized`: Invalid or expired token
- `403 Forbidden`: No authorization header provided

---

### Update Current User

**Endpoint:** `PUT /users/me`

**Description:** Updates the profile information for the currently authenticated user.

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:** `UserUpdate` schema
```json
{
  "username": "string (optional)",
  "email": "string (optional)"
}
```

**Response:** `UserResponse` schema
```json
{
  "id": "uuid",
  "username": "string",
  "email": "string"
}
```

**Authentication:** Required (Bearer Token)

**Status Codes:**
- `200 OK`: User profile updated successfully
- `401 Unauthorized`: Invalid or expired token
- `403 Forbidden`: No authorization header provided
- `409 Conflict`: Username or email already exists
- `422 Unprocessable Entity`: Invalid request data
- `500 Internal Server Error`: Server error

---

### Request Password Reset

**Endpoint:** `POST /users/request-password-reset`

**Description:** Initiates the password reset process by sending a reset link (token) to the user's email.

**Request Body:** `PasswordResetRequest` schema
```json
{
  "email": "string"
}
```

**Response:**
```json
{
  "message": "If a user with that email exists, a password reset link has been sent."
}
```

**Authentication:** None

**Status Codes:**
- `200 OK`: Password reset request processed (generic message returned regardless of email existence)

---

### Reset Password

**Endpoint:** `POST /users/reset-password`

**Description:** Resets the user's password using a valid reset token.

**Request Body:** `PasswordResetConfirm` schema
```json
{
  "token": "string",
  "new_password": "string"
}
```

**Response:**
```json
{
  "message": "Password has been reset successfully."
}
```

**Authentication:** None

**Status Codes:**
- `200 OK`: Password reset successful
- `400 Bad Request`: Invalid or expired password reset token
- `500 Internal Server Error`: Server error

---

## Event Management

The following endpoints handle event management including creation, retrieval, updating, and deletion of calendar events.

**Authentication:** All event management endpoints require JWT authentication (Authorization: Bearer <token>).

**Timezone Handling:** All datetime fields accept ISO 8601 strings with optional timezone information. Naive datetime values are treated as UTC. All-day events are automatically normalized to full-day spans (00:00:00 to 23:59:59.999999).

### Create Event

**Endpoint:** `POST /api/events/`

**Description:** Creates a new calendar event for the authenticated user.

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:** `EventCreate` schema
```json
{
  "title": "string",
  "description": "string (optional)",
  "start_time": "2024-01-15T10:00:00Z",
  "end_time": "2024-01-15T11:00:00Z",
  "category": "string (optional)",
  "is_all_day": false,
  "is_recurring": false,
  "metadata": {"key": "value"}
}
```

**Response:** `EventResponse` schema
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "Team Meeting",
  "description": "Weekly team sync",
  "start_time": "2024-01-15T10:00:00Z",
  "end_time": "2024-01-15T11:00:00Z",
  "category": "work",
  "is_all_day": false,
  "is_recurring": false,
  "metadata": {"priority": "high"},
  "created_at": "2024-01-15T09:00:00Z",
  "updated_at": "2024-01-15T09:00:00Z"
}
```

**Authentication:** Required (Bearer Token)

**Status Codes:**
- `201 Created`: Event created successfully
- `400 Bad Request`: Invalid request data (e.g., end time before start time, empty title)
- `401 Unauthorized`: Invalid or expired token
- `403 Forbidden`: No authorization header provided
- `409 Conflict`: Event time conflicts with existing events
- `500 Internal Server Error`: Server error

---

### Get Event

**Endpoint:** `GET /api/events/{event_id}`

**Description:** Retrieves a single event by its ID. Users can only access their own events.

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Path Parameters:**
- `event_id` (UUID): The unique identifier of the event to retrieve

**Response:** `EventResponse` schema
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "string",
  "description": "string",
  "start_time": "2024-01-15T10:00:00Z",
  "end_time": "2024-01-15T11:00:00Z",
  "category": "string",
  "is_all_day": false,
  "is_recurring": false,
  "metadata": {"key": "value"},
  "created_at": "2024-01-15T09:00:00Z",
  "updated_at": "2024-01-15T09:00:00Z"
}
```

**Authentication:** Required (Bearer Token)

**Status Codes:**
- `200 OK`: Event retrieved successfully
- `401 Unauthorized`: Invalid or expired token
- `403 Forbidden`: No authorization header provided or event belongs to another user
- `404 Not Found`: Event not found
- `500 Internal Server Error`: Server error

---

### Get Events with Filtering

**Endpoint:** `GET /api/events/`

**Description:** Retrieves events for the authenticated user with optional filtering by date range and category.

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Query Parameters:**
- `start_date` (date, optional): Filter events starting from this date (format: YYYY-MM-DD)
- `end_date` (date, optional): Filter events ending before this date (format: YYYY-MM-DD)
- `category` (string, optional): Filter events by category

**Example Request:**
```
GET /api/events/?start_date=2024-01-15&end_date=2024-01-31&category=work
```

**Response:** List of `EventResponse` schemas
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "title": "Team Meeting",
    "description": "Weekly team sync",
    "start_time": "2024-01-15T10:00:00Z",
    "end_time": "2024-01-15T11:00:00Z",
    "category": "work",
    "is_all_day": false,
    "is_recurring": false,
    "metadata": {"priority": "high"},
    "created_at": "2024-01-15T09:00:00Z",
    "updated_at": "2024-01-15T09:00:00Z"
  }
]
```

**Authentication:** Required (Bearer Token)

**Status Codes:**
- `200 OK`: Events retrieved successfully
- `401 Unauthorized`: Invalid or expired token
- `403 Forbidden`: No authorization header provided
- `500 Internal Server Error`: Server error

---

### Update Event

**Endpoint:** `PUT /api/events/{event_id}`

**Description:** Updates an existing event. Users can only update their own events.

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Path Parameters:**
- `event_id` (UUID): The unique identifier of the event to update

**Request Body:** `EventUpdate` schema (all fields optional)
```json
{
  "title": "string (optional)",
  "description": "string (optional)",
  "start_time": "2024-01-15T14:00:00Z (optional)",
  "end_time": "2024-01-15T15:00:00Z (optional)",
  "category": "string (optional)",
  "is_all_day": false,
  "is_recurring": false,
  "metadata": {"key": "value"}
}
```

**Response:** `EventResponse` schema
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "Updated Event Title",
  "description": "Updated description",
  "start_time": "2024-01-15T14:00:00Z",
  "end_time": "2024-01-15T15:00:00Z",
  "category": "work",
  "is_all_day": false,
  "is_recurring": false,
  "metadata": {"priority": "medium"},
  "created_at": "2024-01-15T09:00:00Z",
  "updated_at": "2024-01-15T13:30:00Z"
}
```

**Authentication:** Required (Bearer Token)

**Status Codes:**
- `200 OK`: Event updated successfully
- `400 Bad Request`: Invalid request data (e.g., end time before start time, empty title)
- `401 Unauthorized`: Invalid or expired token
- `403 Forbidden`: No authorization header provided or event belongs to another user
- `404 Not Found`: Event not found
- `409 Conflict`: Event time conflicts with existing events
- `500 Internal Server Error`: Server error

---

### Delete Event

**Endpoint:** `DELETE /api/events/{event_id}`

**Description:** Deletes an event and handles cleanup of associated reminder settings. Users can only delete their own events.

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Path Parameters:**
- `event_id` (UUID): The unique identifier of the event to delete

**Response:** No content (204 status code)

**Authentication:** Required (Bearer Token)

**Status Codes:**
- `204 No Content`: Event deleted successfully
- `401 Unauthorized`: Invalid or expired token
- `403 Forbidden`: No authorization header provided or event belongs to another user
- `404 Not Found`: Event not found
- `500 Internal Server Error`: Server error

---

## Inbox Management Endpoints

The following endpoints handle inbox item management including conversion to calendar events.

**Authentication:** All inbox management endpoints require JWT authentication (Authorization: Bearer <token>).

### Convert Inbox Item to Event

**Endpoint:** `POST /api/inbox/convert_to_event`

**Description:** Converts an existing inbox item into a new calendar event.

**Authentication:** Requires valid JWT bearer token.

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:** `InboxItemConvertToEvent` schema
```json
{
  "item_id": "b1c0b3a7-3e81-4f9e-9d2a-8c5a4d7e6f1a",
  "start_time": "2023-10-27T09:00:00Z",
  "end_time": "2023-10-27T10:00:00Z",
  "event_title": "Follow up on client proposal",
  "is_all_day": false,
  "event_category": "Work",
  "event_metadata": {"origin": "inbox", "priority": "high"}
}
```

**Response:** `EventResponse` schema
```json
{
  "id": "e2f3e4d5-5c7e-4b8f-9a0d-1e2f3a4b5c6d",
  "user_id": "u9d8c7b6-5a4f-3e2d-1c0b-9a8b7c6d5e4f",
  "title": "Follow up on client proposal",
  "description": "(derived from inbox item content)",
  "start_time": "2023-10-27T09:00:00Z",
  "end_time": "2023-10-27T10:00:00Z",
  "category": "Work",
  "is_all_day": false,
  "is_recurring": false,
  "event_metadata": {"converted_from_inbox_item_id": "b1c0b3a7-3e81-4f9e-9d2a-8c5a4d7e6f1a", "origin": "inbox", "priority": "high"},
  "created_at": "2023-10-27T08:50:00Z",
  "updated_at": "2023-10-27T08:50:00Z"
}
```

**Authentication:** Required (Bearer Token)

**Status Codes:**
- `201 Created`: Event created successfully from inbox item
- `400 Bad Request`: If event times are invalid or other input validation fails
- `401 Unauthorized`: If no/invalid JWT token is provided
- `403 Forbidden`: If the token is valid but the user lacks permissions (handled by `get_current_user_dep`)
- `404 Not Found`: If the `item_id` does not exist or is not owned by the authenticated user
- `409 Conflict`: If the new event conflicts with an existing event in the calendar
- `500 Internal Server Error`: For unexpected server issues

### Streamlit Drag-and-Drop Integration Notes

**Client-Side Responsibilities:**
- When an inbox item is dragged and dropped onto a calendar, the Streamlit frontend is responsible for extracting the `item_id` of the dragged inbox item.
- The frontend must determine the `start_time` and `end_time` for the new event based on where the item is dropped on the calendar UI. It should also infer `is_all_day` status.
- These details, along with any optional overrides for `event_title`, `event_description`, `event_category`, `is_recurring`, or `event_metadata`, should be packaged into an `InboxItemConvertToEvent` request body.
- This payload should then be sent to the `POST /api/inbox/convert_to_event` endpoint.

**Post-Conversion:** Upon successful conversion, the client can consider the inbox item's status as updated (e.g., to 'SCHEDULED') and update its local UI accordingly.

---

## Schema Definitions

### UserCreate
- `username`: string - Unique username for the user
- `email`: string - Valid email address for the user
- `password`: string - User's password

### UserLogin
- `username_or_email`: string - Username or email address for login
- `password`: string - User's password

### UserUpdate
- `username`: string (optional) - New username for the user
- `email`: string (optional) - New email address for the user

### UserResponse
- `id`: UUID - Unique identifier for the user
- `username`: string - User's username
- `email`: string - User's email address

### Token
- `access_token`: string - JWT access token for authentication
- `token_type`: string - Token type (always "bearer")

### PasswordResetRequest
- `email`: string - Email address to send password reset link to

### PasswordResetConfirm
- `token`: string - Password reset token received via email
- `new_password`: string - New password to set for the user

### EventCreate
- `title`: string - Event title (required)
- `description`: string (optional) - Event description
- `start_time`: datetime - Event start time in ISO 8601 format
- `end_time`: datetime - Event end time in ISO 8601 format
- `category`: string (optional) - Event category
- `is_all_day`: boolean - Whether the event is an all-day event (default: false)
- `is_recurring`: boolean - Whether the event is recurring (default: false)
- `metadata`: object (optional) - Additional event metadata as key-value pairs

### EventUpdate
- `title`: string (optional) - New event title
- `description`: string (optional) - New event description
- `start_time`: datetime (optional) - New event start time in ISO 8601 format
- `end_time`: datetime (optional) - New event end time in ISO 8601 format
- `category`: string (optional) - New event category
- `is_all_day`: boolean (optional) - Whether the event is an all-day event
- `is_recurring`: boolean (optional) - Whether the event is recurring
- `metadata`: object (optional) - New event metadata as key-value pairs

### EventResponse
- `id`: UUID - Unique identifier for the event
- `user_id`: UUID - ID of the user who owns the event
- `title`: string - Event title
- `description`: string - Event description
- `start_time`: datetime - Event start time in ISO 8601 format
- `end_time`: datetime - Event end time in ISO 8601 format
- `category`: string - Event category
- `is_all_day`: boolean - Whether the event is an all-day event
- `is_recurring`: boolean - Whether the event is recurring
- `metadata`: object - Event metadata as key-value pairs
- `created_at`: datetime - Event creation timestamp
- `updated_at`: datetime - Event last update timestamp

### EventFilter
- `start_date`: date (optional) - Filter events starting from this date
- `end_date`: date (optional) - Filter events ending before this date
- `category`: string (optional) - Filter events by category

### InboxItemConvertToEvent
- `item_id`: UUID - The ID of the inbox item to convert (required)
- `start_time`: datetime - Start time of the new calendar event in ISO 8601 format (required)
- `end_time`: datetime - End time of the new calendar event in ISO 8601 format (required)
- `event_title`: string (optional) - Optional title for the event. Defaults to inbox item content if not provided
- `event_description`: string (optional) - Optional description for the event. Defaults to inbox item content if not provided and content is short, or empty
- `is_all_day`: boolean - Whether the event is an all-day event (default: false)
- `is_recurring`: boolean - Whether the event is a recurring event (default: false)
- `event_category`: string (optional) - Optional category for the event. Defaults to inbox item category if not provided
- `event_metadata`: object (optional) - Optional metadata for the event. The original inbox item ID will be included here automatically

---

## WebSocket API

This section documents the real-time WebSocket API exposed by the FlowState service. The WebSocket endpoint enables live synchronization of events and inbox items between clients and the server.

### Overview

- Top-level WebSocket endpoint: `/ws/sync`
- Purpose: Real-time data synchronization for event and inbox changes, plus control and heartbeat messages.
- Multiple concurrent connections per user are supported (e.g., multiple browser tabs or devices).
- Tests that exercise the implementation live under `tests/api/test_websocket_router.py`.

### Endpoint: /ws/sync

**Method:** WebSocket (GET upgrade)

**Connection URL (example):**

```
ws://localhost:8000/ws/sync?token={YOUR_JWT_TOKEN}
```

- token is a JWT access token passed as a query parameter.
- The JWT access token can be obtained from the standard login endpoint: `POST /users/login` which returns an access_token.
- Note: REST endpoints typically accept Authorization: Bearer <token> headers. For this WS endpoint the token is passed as a query parameter for the initial handshake.

### Authentication

- JWT authentication is required for the `/ws/sync` endpoint.
- Clients MUST include a valid JWT as the `token` query parameter when opening the WebSocket.
- The server validates the token during the initial handshake and will reject the connection (close) if the token is missing or invalid. In the current implementation the server closes with a policy violation / unauthorized code (1008) on invalid/missing tokens.
- How to obtain a token: call `POST /users/login` and use the returned `access_token`.

### Message Format (Standardized JSON)

All messages exchanged over the WebSocket use a standardized JSON envelope. Both client->server and server->client messages follow the same basic shape.

Example structure:

```json
{
  "type": "event_update", // e.g., event_update, inbox_update, ping, pong, ack, error
  "payload": {
    // type-specific data
  }
}
```

Common type values and semantics:

- `event_update` — event-related update (client can notify server of changes)
- `inbox_update` — inbox item updates or actions
- `ping` — health-check ping message
- `pong` — pong response to ping
- `ack` — acknowledgment from server responding to a client message. Example payload: `{ "received_type": "event_update", "status": "ok" }`
- `error` — error message from server. Example payload: `{ "detail": "invalid_message" }`

Validation and error behavior:

- Invalid JSON or messages that do not match the expected schema will prompt an `error` message from the server with payload.detail set to values such as `invalid_message` or `invalid_json`.
- Unknown `type` values are responded to with an `error` message of `unknown_type`.
- Internal server errors in message handling result in `error` messages with `internal_error` detail.

### Connection Lifecycle

- Connect: Client opens a WebSocket to `/ws/sync?token=...`.
- Auth: Server validates the token before accepting. If token validation fails the server closes the connection (policy violation / 1008 recommended).
- Accept: On successful validation the server accepts the WebSocket upgrade and registers the connection in its connection registry.
- Messaging: After accept, client and server exchange JSON messages using the standardized envelope.
- Disconnection: When a client disconnects or when the server detects an error/heartbeat timeout, the server removes the connection from the registry and cleans up resources.
- Cleanup codes: The implementation performs a graceful close where possible; heartbeat timeouts trigger a server-side close (custom close code used internally).

### Heartbeat (Ping/Pong)

- The server periodically sends JSON ping messages to clients to verify connection health. The default configuration values are defined in the application's config (see `src/fs_flowstate_svc/config.py`):
  - WS_PING_INTERVAL_SECONDS: 15
  - WS_PONG_TIMEOUT_SECONDS: 45

- Server ping message example:

```json
{ "type": "ping", "payload": {} }
```

- Clients should respond with a pong message:

```json
{ "type": "pong", "payload": {} }
```

- If the server does not receive a pong within WS_PONG_TIMEOUT_SECONDS after sending a ping, it will consider the connection unhealthy and close it.
- Clients MAY also initiate ping messages and expect a `pong` response.

### Security Considerations

- Use secure WebSocket (wss://) in production to protect JWT tokens in transit.
- Passing tokens in the query string has inherent exposure risks (e.g., logs, proxy caches). Treat tokens as secrets and avoid logging full URLs containing tokens.
- Prefer short-lived access tokens and refresh tokens via your standard auth flows.
- Ensure reverse proxies (NGINX / load balancers) correctly handle WebSocket upgrade headers and terminate TLS properly.
- Do not persist or display JWT tokens in client logs or dashboards.

### Usage Examples

Python example using the `websockets` library:

```python
import asyncio
import json
import websockets

async def main():
    token = "YOUR_JWT"
    url = f"ws://localhost:8000/ws/sync?token={token}"
    async with websockets.connect(url) as ws:
        # receive a server ping and respond with pong
        msg = json.loads(await ws.recv())
        if msg.get("type") == "ping":
            await ws.send(json.dumps({"type": "pong", "payload": {}}))

        # send an event update
        await ws.send(json.dumps({"type": "event_update", "payload": {"id": 1}}))
        ack = json.loads(await ws.recv())
        print("ACK:", ack)

asyncio.run(main())
```

JavaScript (browser) example:

```javascript
const token = "YOUR_JWT";
const ws = new WebSocket(`ws://localhost:8000/ws/sync?token=${token}`);

ws.onopen = () => { console.log("connected"); };

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === "ping") {
    ws.send(JSON.stringify({ type: "pong", payload: {} }));
  } else {
    console.log("received:", msg);
  }
};

ws.onerror = (e) => console.error("ws error", e);

function sendInboxUpdate() {
  ws.send(JSON.stringify({ type: "inbox_update", payload: { item: 123 } }));
}
```

### Testing and Notes to Developers

- The server-side implementation and tests live in `src/fs_flowstate_svc/api/websocket_router.py` and `tests/api/test_websocket_router.py`.
- Tests assert authentication, message validation, routing (ack), heartbeat (ping/pong), and connection registry behavior.
- Keep documentation synced with implementation to avoid drift, particularly around the token passing mechanism and heartbeat configuration.

---

