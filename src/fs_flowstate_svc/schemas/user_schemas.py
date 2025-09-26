"""Pydantic schemas for user-related operations."""

import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema with common fields."""
    username: str
    email: str


class UserCreate(UserBase):
    """Schema for user creation with password."""
    password: str


class UserLogin(BaseModel):
    """Schema for user login."""
    username_or_email: str
    password: str


class UserUpdate(BaseModel):
    """Schema for user profile updates. Password updates are handled via reset_password endpoint."""
    username: Optional[str] = None
    email: Optional[str] = None


class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""
    email: str


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""
    token: str
    new_password: str


class UserResponse(UserBase):
    """Schema for user response with ID."""
    id: uuid.UUID
    
    class Config:
        from_attributes = True
