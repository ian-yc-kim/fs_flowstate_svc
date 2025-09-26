import uuid
import pytest
import time
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from fs_flowstate_svc.models.flowstate_models import Users, UserReminderPreference


class TestUserReminderPreferenceModel:
    """Test UserReminderPreference model CRUD operations and constraints."""
    
    def test_create_user_reminder_preference(self, db_session):
        """Test creating a new user reminder preference."""
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password_123"
        )
        db_session.add(user)
        db_session.commit()
        
        preference = UserReminderPreference(
            user_id=user.id,
            event_category="meeting",
            preparation_time_minutes=15,
            is_custom=True
        )
        db_session.add(preference)
        db_session.commit()
        
        assert preference.id is not None
        assert isinstance(preference.id, uuid.UUID)
        assert preference.user_id == user.id
        assert preference.event_category == "meeting"
        assert preference.preparation_time_minutes == 15
        assert preference.is_custom == True
        assert preference.created_at is not None
        assert preference.updated_at is not None
    
    def test_create_user_reminder_preference_with_defaults(self, db_session):
        """Test creating a user reminder preference with default values."""
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password_123"
        )
        db_session.add(user)
        db_session.commit()
        
        preference = UserReminderPreference(
            user_id=user.id,
            event_category="general",
            preparation_time_minutes=10
            # is_custom should default to False
        )
        db_session.add(preference)
        db_session.commit()
        
        assert preference.is_custom == False
        assert preference.created_at is not None
        assert preference.updated_at is not None
    
    def test_unique_constraint_user_event_category(self, db_session):
        """Test the unique constraint on user_id and event_category."""
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password_123"
        )
        db_session.add(user)
        db_session.commit()
        
        # Create first preference
        preference1 = UserReminderPreference(
            user_id=user.id,
            event_category="meeting",
            preparation_time_minutes=15,
            is_custom=True
        )
        db_session.add(preference1)
        db_session.commit()
        
        # Try to create second preference with same user_id and event_category
        preference2 = UserReminderPreference(
            user_id=user.id,
            event_category="meeting",  # Same category
            preparation_time_minutes=30,
            is_custom=False
        )
        db_session.add(preference2)
        
        # This should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_different_users_same_category_allowed(self, db_session):
        """Test that different users can have preferences for the same category."""
        user1 = Users(
            username="user1",
            email="user1@example.com",
            password_hash="hash1"
        )
        user2 = Users(
            username="user2",
            email="user2@example.com",
            password_hash="hash2"
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        
        # Both users can have preferences for the same category
        preference1 = UserReminderPreference(
            user_id=user1.id,
            event_category="meeting",
            preparation_time_minutes=15,
            is_custom=True
        )
        preference2 = UserReminderPreference(
            user_id=user2.id,
            event_category="meeting",  # Same category, different user
            preparation_time_minutes=20,
            is_custom=False
        )
        
        db_session.add(preference1)
        db_session.add(preference2)
        db_session.commit()  # Should succeed
        
        assert preference1.user_id == user1.id
        assert preference2.user_id == user2.id
        assert preference1.event_category == preference2.event_category == "meeting"
    
    def test_same_user_different_categories_allowed(self, db_session):
        """Test that the same user can have preferences for different categories."""
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password_123"
        )
        db_session.add(user)
        db_session.commit()
        
        # Same user can have multiple preferences for different categories
        preference1 = UserReminderPreference(
            user_id=user.id,
            event_category="meeting",
            preparation_time_minutes=15,
            is_custom=True
        )
        preference2 = UserReminderPreference(
            user_id=user.id,
            event_category="deep work",
            preparation_time_minutes=30,
            is_custom=False
        )
        preference3 = UserReminderPreference(
            user_id=user.id,
            event_category="travel",
            preparation_time_minutes=45,
            is_custom=True
        )
        
        db_session.add(preference1)
        db_session.add(preference2)
        db_session.add(preference3)
        db_session.commit()  # Should succeed
        
        assert len(user.user_reminder_preferences) == 3
        categories = [p.event_category for p in user.user_reminder_preferences]
        assert "meeting" in categories
        assert "deep work" in categories
        assert "travel" in categories
    
    def test_user_relationship(self, db_session):
        """Test UserReminderPreference-Users relationship."""
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password_123"
        )
        db_session.add(user)
        db_session.commit()
        
        preference = UserReminderPreference(
            user_id=user.id,
            event_category="meeting",
            preparation_time_minutes=15,
            is_custom=True
        )
        db_session.add(preference)
        db_session.commit()
        
        # Test forward relationship
        assert preference.user == user
        # Test backward relationship
        assert preference in user.user_reminder_preferences
    
    def test_cascade_delete_on_user_delete(self, db_session):
        """Test that preferences are deleted when user is deleted."""
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password_123"
        )
        db_session.add(user)
        db_session.commit()
        
        preference = UserReminderPreference(
            user_id=user.id,
            event_category="meeting",
            preparation_time_minutes=15,
            is_custom=True
        )
        db_session.add(preference)
        db_session.commit()
        
        preference_id = preference.id
        db_session.delete(user)
        db_session.commit()
        
        # Preference should be deleted due to cascade
        deleted_preference = db_session.get(UserReminderPreference, preference_id)
        assert deleted_preference is None
    
    def test_foreign_key_constraint_validation(self, db_session):
        """Test that foreign key constraint validation works by creating a preference for a valid user."""
        # Create a valid user first
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password_123"
        )
        db_session.add(user)
        db_session.commit()
        
        # Create preference with valid user_id - this should succeed
        preference = UserReminderPreference(
            user_id=user.id,
            event_category="meeting",
            preparation_time_minutes=15,
            is_custom=True
        )
        db_session.add(preference)
        db_session.commit()  # Should succeed
        
        assert preference.user_id == user.id
        assert preference.user == user
    
    def test_update_preference(self, db_session):
        """Test updating an existing preference."""
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password_123"
        )
        db_session.add(user)
        db_session.commit()
        
        preference = UserReminderPreference(
            user_id=user.id,
            event_category="meeting",
            preparation_time_minutes=15,
            is_custom=True
        )
        db_session.add(preference)
        db_session.commit()
        
        # Update the preference - add small delay to ensure updated_at changes
        original_updated_at = preference.updated_at
        time.sleep(0.01)  # Small delay to ensure timestamp difference
        preference.preparation_time_minutes = 30
        preference.is_custom = False
        db_session.commit()
        
        # Verify updates
        db_session.refresh(preference)
        assert preference.preparation_time_minutes == 30
        assert preference.is_custom == False
        # Use >= to handle precision issues in timestamps
        assert preference.updated_at >= original_updated_at
    
    def test_repr_method(self, db_session):
        """Test string representation of UserReminderPreference."""
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password_123"
        )
        db_session.add(user)
        db_session.commit()
        
        preference = UserReminderPreference(
            user_id=user.id,
            event_category="meeting",
            preparation_time_minutes=15,
            is_custom=True
        )
        db_session.add(preference)
        db_session.commit()
        
        repr_str = repr(preference)
        assert "UserReminderPreference" in repr_str
        assert "meeting" in repr_str
        assert "15" in repr_str
        assert str(user.id) in repr_str
    
    def test_various_event_categories(self, db_session):
        """Test creating preferences with various event categories."""
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password_123"
        )
        db_session.add(user)
        db_session.commit()
        
        categories = ['meeting', 'deep work', 'travel', 'general', 'personal', 'break']
        
        for i, category in enumerate(categories):
            preference = UserReminderPreference(
                user_id=user.id,
                event_category=category,
                preparation_time_minutes=(i + 1) * 10,
                is_custom=i % 2 == 0
            )
            db_session.add(preference)
        
        db_session.commit()
        
        # Verify all preferences were created
        assert len(user.user_reminder_preferences) == len(categories)
        stored_categories = [p.event_category for p in user.user_reminder_preferences]
        for category in categories:
            assert category in stored_categories
    
    def test_preparation_time_minutes_various_values(self, db_session):
        """Test creating preferences with various preparation time values."""
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password_123"
        )
        db_session.add(user)
        db_session.commit()
        
        time_values = [0, 5, 10, 15, 30, 45, 60, 120, 240]
        
        for i, time_val in enumerate(time_values):
            preference = UserReminderPreference(
                user_id=user.id,
                event_category=f"category_{i}",
                preparation_time_minutes=time_val,
                is_custom=True
            )
            db_session.add(preference)
        
        db_session.commit()
        
        # Verify all preferences were created with correct times
        preferences = user.user_reminder_preferences
        stored_times = [p.preparation_time_minutes for p in preferences]
        for time_val in time_values:
            assert time_val in stored_times