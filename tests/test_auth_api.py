"""Integration tests for authentication API endpoints."""

import pytest
from datetime import datetime, timedelta
from fastapi import status

from fs_flowstate_svc.models.flowstate_models import Users
from fs_flowstate_svc.schemas.user_schemas import UserCreate
from fs_flowstate_svc.services.user_service import create_user, generate_password_reset_token
from fs_flowstate_svc.auth.jwt_handler import create_access_token


class TestAuthAPI:
    """Integration tests for authentication API endpoints."""
    
    def test_register_success(self, client, monkeypatch):
        """Test successful user registration."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123"
        }
        
        response = client.post("/auth/register", json=user_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "id" in data
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert "password" not in data  # Password should not be in response
    
    def test_register_duplicate_username(self, client, db_session, monkeypatch):
        """Test registration failure with duplicate username."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create existing user
        existing_user = UserCreate(
            username="duplicate",
            email="first@example.com",
            password="password123"
        )
        create_user(db_session, existing_user)
        
        # Try to register with same username but different email
        user_data = {
            "username": "duplicate",
            "email": "second@example.com",
            "password": "password123"
        }
        
        response = client.post("/auth/register", json=user_data)
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "Username or email already exists" in response.json()["detail"]
    
    def test_register_duplicate_email(self, client, db_session, monkeypatch):
        """Test registration failure with duplicate email."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create existing user
        existing_user = UserCreate(
            username="first",
            email="duplicate@example.com",
            password="password123"
        )
        create_user(db_session, existing_user)
        
        # Try to register with same email but different username
        user_data = {
            "username": "second",
            "email": "duplicate@example.com",
            "password": "password123"
        }
        
        response = client.post("/auth/register", json=user_data)
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "Username or email already exists" in response.json()["detail"]
    
    def test_register_invalid_data(self, client, monkeypatch):
        """Test registration failure with missing required fields."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Missing password field
        user_data = {
            "username": "incompleteuser",
            "email": "incomplete@example.com"
        }
        
        response = client.post("/auth/register", json=user_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_login_success(self, client, db_session, monkeypatch):
        """Test successful login with correct credentials."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create user for login
        user_data = UserCreate(
            username="loginuser",
            email="login@example.com",
            password="correct_password"
        )
        create_user(db_session, user_data)
        
        # Test login with username
        login_data = {
            "username_or_email": "loginuser",
            "password": "correct_password"
        }
        
        response = client.post("/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0
        
        # Test login with email
        login_data = {
            "username_or_email": "login@example.com",
            "password": "correct_password"
        }
        
        response = client.post("/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_incorrect_password(self, client, db_session, monkeypatch):
        """Test login failure with incorrect password."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create user for login
        user_data = UserCreate(
            username="wrongpassuser",
            email="wrongpass@example.com",
            password="correct_password"
        )
        create_user(db_session, user_data)
        
        # Try to login with wrong password
        login_data = {
            "username_or_email": "wrongpassuser",
            "password": "wrong_password"
        }
        
        response = client.post("/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Incorrect username or password" in response.json()["detail"]
    
    def test_login_nonexistent_user(self, client, monkeypatch):
        """Test login failure with non-existent user."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        login_data = {
            "username_or_email": "nonexistent",
            "password": "any_password"
        }
        
        response = client.post("/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Incorrect username or password" in response.json()["detail"]
    
    def test_get_current_user_success(self, client, db_session, monkeypatch):
        """Test successful retrieval of current user with valid token."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create user
        user_data = UserCreate(
            username="currentuser",
            email="current@example.com",
            password="password123"
        )
        created_user = create_user(db_session, user_data)
        
        # Login to get token
        login_data = {
            "username_or_email": "currentuser",
            "password": "password123"
        }
        login_response = client.post("/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        
        # Get current user info
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/auth/me", headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(created_user.id)
        assert data["username"] == "currentuser"
        assert data["email"] == "current@example.com"
    
    def test_get_current_user_no_token(self, client, monkeypatch):
        """Test failure to get current user with no authorization token."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        response = client.get("/auth/me")
        
        # HTTPBearer returns 403 Forbidden when no Authorization header is provided
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_get_current_user_invalid_token(self, client, monkeypatch):
        """Test failure to get current user with invalid token."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        headers = {"Authorization": "Bearer invalid.token.here"}
        response = client.get("/auth/me", headers=headers)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in response.json()["detail"]
    
    def test_get_current_user_expired_token(self, client, db_session, monkeypatch):
        """Test failure to get current user with expired token."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create user
        user_data = UserCreate(
            username="expireduser",
            email="expired@example.com",
            password="password123"
        )
        created_user = create_user(db_session, user_data)
        
        # Create expired token
        expired_token = create_access_token(
            data={"sub": str(created_user.id)},
            expires_delta=timedelta(seconds=-1)
        )
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/auth/me", headers=headers)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in response.json()["detail"]
    
    def test_request_password_reset_existing_email(self, client, db_session, monkeypatch):
        """Test password reset request for existing email."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create user
        user_data = UserCreate(
            username="resetuser",
            email="reset@example.com",
            password="password123"
        )
        created_user = create_user(db_session, user_data)
        
        # Request password reset
        reset_data = {"email": "reset@example.com"}
        response = client.post("/auth/request-password-reset", json=reset_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "If a user with that email exists, a password reset link has been sent." in data["message"]
        
        # Verify token was generated in database
        db_session.refresh(created_user)
        assert created_user.password_reset_token is not None
        assert created_user.password_reset_expires_at is not None
        assert created_user.password_reset_expires_at > datetime.utcnow()
    
    def test_request_password_reset_nonexistent_email(self, client, db_session, monkeypatch):
        """Test password reset request for non-existent email returns generic message."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Request password reset for non-existent email
        reset_data = {"email": "nonexistent@example.com"}
        response = client.post("/auth/request-password-reset", json=reset_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should return same generic message to prevent email enumeration
        assert "If a user with that email exists, a password reset link has been sent." in data["message"]
    
    def test_reset_password_success(self, client, db_session, monkeypatch):
        """Test successful password reset with valid token."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create user
        user_data = UserCreate(
            username="pwresetuser",
            email="pwreset@example.com",
            password="old_password"
        )
        created_user = create_user(db_session, user_data)
        
        # Generate password reset token
        reset_token = generate_password_reset_token(db_session, "pwreset@example.com")
        
        # Reset password
        reset_data = {
            "token": reset_token,
            "new_password": "new_password_123"
        }
        response = client.post("/auth/reset-password", json=reset_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "Password has been reset successfully." in data["message"]
        
        # Verify password was updated and reset fields cleared
        db_session.refresh(created_user)
        assert created_user.password_reset_token is None
        assert created_user.password_reset_expires_at is None
        
        # Verify new password works by logging in
        login_data = {
            "username_or_email": "pwresetuser",
            "password": "new_password_123"
        }
        login_response = client.post("/auth/login", json=login_data)
        assert login_response.status_code == status.HTTP_200_OK
    
    def test_reset_password_invalid_token(self, client, monkeypatch):
        """Test password reset failure with invalid token."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        reset_data = {
            "token": "invalid_token_12345",
            "new_password": "new_password"
        }
        response = client.post("/auth/reset-password", json=reset_data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid or expired password reset token" in response.json()["detail"]
    
    def test_reset_password_expired_token(self, client, db_session, monkeypatch):
        """Test password reset failure with expired token."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create user
        user_data = UserCreate(
            username="expiredresetuser",
            email="expiredreset@example.com",
            password="password123"
        )
        created_user = create_user(db_session, user_data)
        
        # Manually set expired reset token
        expired_token = "expired_token_12345"
        created_user.password_reset_token = expired_token
        created_user.password_reset_expires_at = datetime.utcnow() - timedelta(hours=1)
        db_session.commit()
        
        # Try to reset password with expired token
        reset_data = {
            "token": expired_token,
            "new_password": "new_password"
        }
        response = client.post("/auth/reset-password", json=reset_data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid or expired password reset token" in response.json()["detail"]
