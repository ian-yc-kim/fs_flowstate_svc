"""Unit tests for user service functions."""

import pytest
import uuid
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from fs_flowstate_svc.models.flowstate_models import Users
from fs_flowstate_svc.schemas.user_schemas import UserCreate, UserLogin
from fs_flowstate_svc.services.user_service import (
    get_user_by_username_or_email,
    create_user,
    authenticate_user,
    login_for_access_token,
    get_current_user,
    generate_password_reset_token,
    reset_user_password
)


class TestUserService:
    """Test suite for user service functions."""
    
    def test_create_user_success_hashes_password(self, db_session, monkeypatch):
        """Test that create_user successfully creates a user with hashed password."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="plain_password_123"
        )
        
        created_user = create_user(db_session, user_data)
        
        # User should be created with correct data
        assert created_user.username == "testuser"
        assert created_user.email == "test@example.com"
        assert created_user.id is not None
        
        # Password should be hashed (not equal to plain password)
        assert created_user.password_hash != "plain_password_123"
        # Should be a bcrypt hash
        assert created_user.password_hash.startswith(("$2b$", "$2a$"))
    
    def test_create_user_duplicate_raises(self, db_session, monkeypatch):
        """Test that create_user raises ValueError for duplicate username/email."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        user_data = UserCreate(
            username="duplicate_user",
            email="duplicate@example.com",
            password="password123"
        )
        
        # Create first user
        create_user(db_session, user_data)
        
        # Try to create second user with same username
        with pytest.raises(ValueError, match="Username or email already exists"):
            create_user(db_session, user_data)
    
    def test_get_user_by_username_or_email(self, db_session, monkeypatch):
        """Test getting user by username or email."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        user_data = UserCreate(
            username="findme",
            email="findme@example.com",
            password="password123"
        )
        created_user = create_user(db_session, user_data)
        
        # Find by username
        found_by_username = get_user_by_username_or_email(db_session, "findme")
        assert found_by_username is not None
        assert found_by_username.id == created_user.id
        
        # Find by email
        found_by_email = get_user_by_username_or_email(db_session, "findme@example.com")
        assert found_by_email is not None
        assert found_by_email.id == created_user.id
        
        # Not found
        not_found = get_user_by_username_or_email(db_session, "nonexistent")
        assert not_found is None
    
    def test_authenticate_user_correct_and_incorrect(self, db_session, monkeypatch):
        """Test user authentication with correct and incorrect credentials."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        user_data = UserCreate(
            username="authuser",
            email="auth@example.com",
            password="correct_password"
        )
        created_user = create_user(db_session, user_data)
        
        # Correct password
        authenticated_user = authenticate_user(db_session, "authuser", "correct_password")
        assert authenticated_user is not None
        assert authenticated_user.id == created_user.id
        
        # Incorrect password
        failed_auth = authenticate_user(db_session, "authuser", "wrong_password")
        assert failed_auth is None
        
        # Nonexistent user
        no_user = authenticate_user(db_session, "nonexistent", "any_password")
        assert no_user is None
    
    def test_login_for_access_token_success(self, db_session, monkeypatch):
        """Test that login_for_access_token returns Token for valid credentials."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        user_data = UserCreate(
            username="loginuser",
            email="login@example.com",
            password="login_password"
        )
        create_user(db_session, user_data)
        
        token = login_for_access_token(db_session, "loginuser", "login_password")
        
        assert token is not None
        assert token.access_token is not None
        assert len(token.access_token) > 0
        assert token.token_type == "bearer"
    
    def test_login_for_access_token_invalid_returns_none(self, db_session, monkeypatch):
        """Test that login_for_access_token returns None for invalid credentials."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        user_data = UserCreate(
            username="loginuser2",
            email="login2@example.com",
            password="correct_password"
        )
        create_user(db_session, user_data)
        
        # Invalid password
        token = login_for_access_token(db_session, "loginuser2", "wrong_password")
        assert token is None
        
        # Invalid username
        token = login_for_access_token(db_session, "nonexistent", "any_password")
        assert token is None
    
    def test_get_current_user_valid_invalid_expired(self, db_session, monkeypatch):
        """Test get_current_user with valid, invalid, and expired tokens."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        user_data = UserCreate(
            username="currentuser",
            email="current@example.com",
            password="password123"
        )
        created_user = create_user(db_session, user_data)
        
        # Valid token
        token_obj = login_for_access_token(db_session, "currentuser", "password123")
        current_user = get_current_user(db_session, token_obj.access_token)
        assert current_user.id == created_user.id
        
        # Invalid token
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(db_session, "invalid.token.here")
        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail
        
        # Test with expired token (create token with past expiry)
        from fs_flowstate_svc.auth.jwt_handler import create_access_token
        expired_token = create_access_token(
            {"sub": str(created_user.id)}, 
            expires_delta=timedelta(seconds=-1)
        )
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(db_session, expired_token)
        assert exc_info.value.status_code == 401
    
    def test_generate_password_reset_token_sets_token_and_expiry(self, db_session, monkeypatch):
        """Test that generate_password_reset_token sets token and expiry."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        user_data = UserCreate(
            username="resetuser",
            email="reset@example.com",
            password="password123"
        )
        created_user = create_user(db_session, user_data)
        
        # Generate reset token
        reset_token = generate_password_reset_token(db_session, "reset@example.com")
        
        assert reset_token is not None
        assert len(reset_token) > 0
        
        # Refresh user from database
        db_session.refresh(created_user)
        
        # Check that token and expiry are set
        assert created_user.password_reset_token == reset_token
        assert created_user.password_reset_expires_at is not None
        assert created_user.password_reset_expires_at > datetime.utcnow()
    
    def test_generate_password_reset_token_nonexistent_email(self, db_session, monkeypatch):
        """Test that generate_password_reset_token returns None for nonexistent email."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        reset_token = generate_password_reset_token(db_session, "nonexistent@example.com")
        assert reset_token is None
    
    def test_reset_user_password_success_and_clears_fields(self, db_session, monkeypatch):
        """Test that reset_user_password updates password and clears reset fields."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        user_data = UserCreate(
            username="pwresetuser",
            email="pwreset@example.com",
            password="old_password"
        )
        created_user = create_user(db_session, user_data)
        old_password_hash = created_user.password_hash
        
        # Generate reset token
        reset_token = generate_password_reset_token(db_session, "pwreset@example.com")
        
        # Reset password
        success = reset_user_password(db_session, reset_token, "new_password_123")
        
        assert success is True
        
        # Refresh user from database
        db_session.refresh(created_user)
        
        # Check password was updated
        assert created_user.password_hash != old_password_hash
        
        # Check reset fields are cleared
        assert created_user.password_reset_token is None
        assert created_user.password_reset_expires_at is None
        
        # Verify new password works
        authenticated = authenticate_user(db_session, "pwresetuser", "new_password_123")
        assert authenticated is not None
    
    def test_reset_user_password_invalid_or_expired_fails(self, db_session, monkeypatch):
        """Test that reset_user_password fails for invalid or expired tokens."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        user_data = UserCreate(
            username="expireuser",
            email="expire@example.com",
            password="password123"
        )
        created_user = create_user(db_session, user_data)
        
        # Test invalid token
        success = reset_user_password(db_session, "invalid_token", "new_password")
        assert success is False
        
        # Test expired token (manually set expired token)
        from datetime import datetime
        created_user.password_reset_token = "expired_token"
        created_user.password_reset_expires_at = datetime.utcnow() - timedelta(hours=1)
        db_session.commit()
        
        success = reset_user_password(db_session, "expired_token", "new_password")
        assert success is False
