# API Documentation

This document provides detailed information about the API endpoints available in the FlowState service.

## Authentication

The following endpoints handle user authentication, registration, and password management.

### Register User

**Endpoint:** `POST /auth/register`

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

**Endpoint:** `POST /auth/login`

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

**Endpoint:** `GET /auth/me`

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

### Request Password Reset

**Endpoint:** `POST /auth/request-password-reset`

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

**Endpoint:** `POST /auth/reset-password`

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

## Schema Definitions

### UserCreate
- `username`: string - Unique username for the user
- `email`: string - Valid email address for the user
- `password`: string - User's password

### UserLogin
- `username_or_email`: string - Username or email address for login
- `password`: string - User's password

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
