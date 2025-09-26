"""Unit tests for update_user service function."""

import pytest
import uuid
from fastapi import HTTPException

from fs_flowstate_svc.models.flowstate_models import Users
from fs_flowstate_svc.schemas.user_schemas import UserCreate, UserUpdate
from fs_flowstate_svc.services.user_service import create_user, update_user


class TestUpdateUser:
    """Test suite for update_user service function."""

    def test_update_user_not_found_raises_404(self, db_session, monkeypatch):
        """Test that update_user raises HTTPException 404 for nonexistent user."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Use a random UUID that doesn't exist
        random_user_id = uuid.uuid4()
        user_update = UserUpdate(username="new_username")
        
        with pytest.raises(HTTPException) as exc_info:
            update_user(db_session, random_user_id, user_update)
        
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "User not found"

    def test_update_user_username_success(self, db_session, monkeypatch):
        """Test successful username update."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create a test user
        user_data = UserCreate(
            username="original_username",
            email="test@example.com",
            password="password123"
        )
        created_user = create_user(db_session, user_data)
        original_updated_at = created_user.updated_at
        
        # Update username
        user_update = UserUpdate(username="new_unique_username")
        updated_user = update_user(db_session, created_user.id, user_update)
        
        # Verify username was updated
        assert updated_user.username == "new_unique_username"
        assert updated_user.email == "test@example.com"  # email unchanged
        assert updated_user.id == created_user.id
        
        # Verify the change persists in database
        db_session.refresh(updated_user)
        assert updated_user.username == "new_unique_username"
        # updated_at should be newer
        assert updated_user.updated_at >= original_updated_at

    def test_update_user_email_success(self, db_session, monkeypatch):
        """Test successful email update."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create a test user
        user_data = UserCreate(
            username="testuser",
            email="original@example.com",
            password="password123"
        )
        created_user = create_user(db_session, user_data)
        original_updated_at = created_user.updated_at
        
        # Update email
        user_update = UserUpdate(email="new_unique@example.com")
        updated_user = update_user(db_session, created_user.id, user_update)
        
        # Verify email was updated
        assert updated_user.email == "new_unique@example.com"
        assert updated_user.username == "testuser"  # username unchanged
        assert updated_user.id == created_user.id
        
        # Verify the change persists in database
        db_session.refresh(updated_user)
        assert updated_user.email == "new_unique@example.com"
        # updated_at should be newer
        assert updated_user.updated_at >= original_updated_at

    def test_update_user_both_fields_success(self, db_session, monkeypatch):
        """Test successful update of both username and email."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create a test user
        user_data = UserCreate(
            username="original_user",
            email="original@example.com",
            password="password123"
        )
        created_user = create_user(db_session, user_data)
        original_updated_at = created_user.updated_at
        
        # Update both username and email
        user_update = UserUpdate(
            username="new_username_both",
            email="new_email_both@example.com"
        )
        updated_user = update_user(db_session, created_user.id, user_update)
        
        # Verify both fields were updated
        assert updated_user.username == "new_username_both"
        assert updated_user.email == "new_email_both@example.com"
        assert updated_user.id == created_user.id
        
        # Verify the changes persist in database
        db_session.refresh(updated_user)
        assert updated_user.username == "new_username_both"
        assert updated_user.email == "new_email_both@example.com"
        # updated_at should be newer
        assert updated_user.updated_at >= original_updated_at

    def test_update_user_duplicate_username_raises_value_error(self, db_session, monkeypatch):
        """Test that updating to existing username raises ValueError."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create first user
        user1_data = UserCreate(
            username="existing_username",
            email="user1@example.com",
            password="password123"
        )
        create_user(db_session, user1_data)
        
        # Create second user
        user2_data = UserCreate(
            username="different_username",
            email="user2@example.com",
            password="password123"
        )
        user2 = create_user(db_session, user2_data)
        
        # Try to update second user's username to match first user's
        user_update = UserUpdate(username="existing_username")
        
        with pytest.raises(ValueError, match="Username already exists"):
            update_user(db_session, user2.id, user_update)
        
        # Verify second user's username wasn't changed
        db_session.refresh(user2)
        assert user2.username == "different_username"

    def test_update_user_duplicate_email_raises_value_error(self, db_session, monkeypatch):
        """Test that updating to existing email raises ValueError."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create first user
        user1_data = UserCreate(
            username="user1",
            email="existing@example.com",
            password="password123"
        )
        create_user(db_session, user1_data)
        
        # Create second user
        user2_data = UserCreate(
            username="user2",
            email="different@example.com",
            password="password123"
        )
        user2 = create_user(db_session, user2_data)
        
        # Try to update second user's email to match first user's
        user_update = UserUpdate(email="existing@example.com")
        
        with pytest.raises(ValueError, match="Email already exists"):
            update_user(db_session, user2.id, user_update)
        
        # Verify second user's email wasn't changed
        db_session.refresh(user2)
        assert user2.email == "different@example.com"

    def test_update_user_no_changes_returns_user(self, db_session, monkeypatch):
        """Test that update with no changes or same values returns user unchanged."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create a test user
        user_data = UserCreate(
            username="unchanged_user",
            email="unchanged@example.com",
            password="password123"
        )
        created_user = create_user(db_session, user_data)
        original_updated_at = created_user.updated_at
        
        # Update with same values
        user_update = UserUpdate(
            username="unchanged_user",
            email="unchanged@example.com"
        )
        updated_user = update_user(db_session, created_user.id, user_update)
        
        # Verify user is returned but unchanged
        assert updated_user.username == "unchanged_user"
        assert updated_user.email == "unchanged@example.com"
        assert updated_user.id == created_user.id
        
        # updated_at should not change since no actual changes were made
        # (since the function only commits when there are actual changes)
        db_session.refresh(updated_user)
        assert updated_user.updated_at == original_updated_at

    def test_update_user_none_values_no_change(self, db_session, monkeypatch):
        """Test that update with None values makes no changes."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        # Create a test user
        user_data = UserCreate(
            username="no_change_user",
            email="nochange@example.com",
            password="password123"
        )
        created_user = create_user(db_session, user_data)
        original_updated_at = created_user.updated_at
        
        # Update with None values (empty update)
        user_update = UserUpdate()
        updated_user = update_user(db_session, created_user.id, user_update)
        
        # Verify user is returned but unchanged
        assert updated_user.username == "no_change_user"
        assert updated_user.email == "nochange@example.com"
        assert updated_user.id == created_user.id
        
        # updated_at should not change since no changes were made
        db_session.refresh(updated_user)
        assert updated_user.updated_at == original_updated_at
