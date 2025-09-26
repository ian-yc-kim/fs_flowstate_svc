import uuid
import pytest
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from fs_flowstate_svc.models.flowstate_models import Users, Events, InboxItems, ReminderSettings, AISettings


class TestUsersModel:
    """Test Users model CRUD operations and constraints."""
    
    def test_create_user(self, db_session):
        """Test creating a new user."""
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password_123"
        )
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password_hash == "hashed_password_123"
        assert user.created_at is not None
        assert user.updated_at is not None
    
    def test_create_user_with_password_reset_defaults(self, db_session):
        """Test that a user can be created with password_reset_token and password_reset_expires_at as None."""
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password_123"
        )
        db_session.add(user)
        db_session.commit()
        
        # Verify password reset columns default to None
        assert user.password_reset_token is None
        assert user.password_reset_expires_at is None
    
    def test_password_reset_token_can_be_set_and_updated(self, db_session):
        """Test that password_reset_token can be set and updated correctly."""
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password_123"
        )
        db_session.add(user)
        db_session.commit()
        
        # Set password reset token and expiry
        reset_token = "reset_token_123"
        expires_at = datetime.now() + timedelta(hours=1)
        
        user.password_reset_token = reset_token
        user.password_reset_expires_at = expires_at
        db_session.commit()
        
        # Verify the values were set correctly
        db_session.refresh(user)
        assert user.password_reset_token == reset_token
        assert user.password_reset_expires_at == expires_at
        
        # Update the password reset token
        new_reset_token = "new_reset_token_456"
        new_expires_at = datetime.now() + timedelta(hours=2)
        
        user.password_reset_token = new_reset_token
        user.password_reset_expires_at = new_expires_at
        db_session.commit()
        
        # Verify the values were updated correctly
        db_session.refresh(user)
        assert user.password_reset_token == new_reset_token
        assert user.password_reset_expires_at == new_expires_at
    
    def test_password_reset_token_unique_constraint(self, db_session):
        """Test the unique constraint on password_reset_token by attempting to set the same token for two different users."""
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
        
        # Set the same password reset token for both users
        same_token = "duplicate_token_123"
        
        user1.password_reset_token = same_token
        db_session.commit()  # This should succeed
        
        user2.password_reset_token = same_token
        
        # This should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        # Rollback the failed transaction
        db_session.rollback()
        
        # Verify that user1 still has the token and user2 doesn't
        db_session.refresh(user1)
        db_session.refresh(user2)
        assert user1.password_reset_token == same_token
        assert user2.password_reset_token is None
    
    def test_password_reset_token_null_values_allowed(self, db_session):
        """Test that multiple users can have NULL password_reset_token values (unique constraint only applies to non-null)."""
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
        
        # Both users should have NULL password_reset_token by default
        assert user1.password_reset_token is None
        assert user2.password_reset_token is None
        
        # Setting one user's token to None explicitly should not cause issues
        user1.password_reset_token = None
        user2.password_reset_token = None
        db_session.commit()
        
        # Verify both users still have None values
        db_session.refresh(user1)
        db_session.refresh(user2)
        assert user1.password_reset_token is None
        assert user2.password_reset_token is None
    
    def test_username_unique_constraint(self, db_session):
        """Test that username must be unique."""
        user1 = Users(username="testuser", email="test1@example.com", password_hash="hash1")
        user2 = Users(username="testuser", email="test2@example.com", password_hash="hash2")
        
        db_session.add(user1)
        db_session.commit()
        
        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_email_unique_constraint(self, db_session):
        """Test that email must be unique."""
        user1 = Users(username="user1", email="test@example.com", password_hash="hash1")
        user2 = Users(username="user2", email="test@example.com", password_hash="hash2")
        
        db_session.add(user1)
        db_session.commit()
        
        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_user_repr(self, db_session):
        """Test user string representation."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        repr_str = repr(user)
        assert "Users" in repr_str
        assert "testuser" in repr_str
        assert "test@example.com" in repr_str


class TestEventsModel:
    """Test Events model CRUD operations and relationships."""
    
    def test_create_event(self, db_session):
        """Test creating a new event."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=1)
        
        event = Events(
            user_id=user.id,
            title="Test Event",
            description="Test Description",
            start_time=start_time,
            end_time=end_time,
            category="Work",
            is_all_day=False,
            is_recurring=True
        )
        db_session.add(event)
        db_session.commit()
        
        assert event.id is not None
        assert isinstance(event.id, uuid.UUID)
        assert event.user_id == user.id
        assert event.title == "Test Event"
        assert event.description == "Test Description"
        assert event.start_time == start_time
        assert event.end_time == end_time
        assert event.category == "Work"
        assert event.is_all_day == False
        assert event.is_recurring == True
    
    def test_event_metadata_defaults_to_empty_dict(self, db_session):
        """Test that an Events object can be created without specifying event_metadata, and it defaults to an empty dictionary."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        event = Events(
            user_id=user.id,
            title="Test Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1)
        )
        db_session.add(event)
        db_session.commit()
        
        # Verify event_metadata defaults to empty dictionary
        assert event.event_metadata == {}
        
        # Refresh and verify the value persists
        db_session.refresh(event)
        assert event.event_metadata == {}
    
    def test_event_metadata_with_dictionary_value(self, db_session):
        """Test that an Events object can be created with a dictionary value for event_metadata, and it's correctly stored."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        test_metadata = {
            "priority": "high",
            "tags": ["important", "work"],
            "attendees_count": 5,
            "location": "Conference Room A"
        }
        
        event = Events(
            user_id=user.id,
            title="Test Event with Metadata",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            event_metadata=test_metadata
        )
        db_session.add(event)
        db_session.commit()
        
        # Verify event_metadata is stored correctly
        assert event.event_metadata == test_metadata
        
        # Refresh and verify persistence
        db_session.refresh(event)
        assert event.event_metadata == test_metadata
    
    def test_event_metadata_retrieval(self, db_session):
        """Test that an Events object can be retrieved, and its event_metadata field holds the expected dictionary."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        test_metadata = {
            "reminder_sent": True,
            "custom_fields": {
                "budget": 1000,
                "status": "confirmed"
            }
        }
        
        event = Events(
            user_id=user.id,
            title="Retrievable Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            event_metadata=test_metadata
        )
        db_session.add(event)
        db_session.commit()
        
        event_id = event.id
        
        # Retrieve event by ID
        retrieved_event = db_session.get(Events, event_id)
        assert retrieved_event is not None
        assert retrieved_event.event_metadata == test_metadata
    
    def test_event_metadata_with_various_json_types(self, db_session):
        """Test with various JSON-compatible data types within the dictionary (strings, numbers, booleans, lists, nested dictionaries)."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        complex_metadata = {
            "string_field": "test string",
            "integer_field": 42,
            "float_field": 3.14159,
            "boolean_field": True,
            "null_field": None,
            "list_field": ["item1", "item2", 123, True, None],
            "nested_dict": {
                "level2": {
                    "level3": {
                        "deep_value": "deep string",
                        "deep_number": 999
                    }
                },
                "another_field": [1, 2, 3]
            }
        }
        
        event = Events(
            user_id=user.id,
            title="Complex Metadata Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            event_metadata=complex_metadata
        )
        db_session.add(event)
        db_session.commit()
        
        # Verify complex event_metadata is stored and retrieved correctly
        assert event.event_metadata == complex_metadata
        
        # Test retrieval after refresh
        db_session.refresh(event)
        assert event.event_metadata == complex_metadata
        
        # Test specific nested values
        assert event.event_metadata["string_field"] == "test string"
        assert event.event_metadata["integer_field"] == 42
        assert event.event_metadata["float_field"] == 3.14159
        assert event.event_metadata["boolean_field"] == True
        assert event.event_metadata["null_field"] is None
        assert event.event_metadata["list_field"] == ["item1", "item2", 123, True, None]
        assert event.event_metadata["nested_dict"]["level2"]["level3"]["deep_value"] == "deep string"
    
    def test_event_metadata_update(self, db_session):
        """Test that event_metadata can be updated on existing events."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        # Create event with initial event_metadata
        initial_metadata = {"version": 1, "status": "draft"}
        event = Events(
            user_id=user.id,
            title="Updatable Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            event_metadata=initial_metadata
        )
        db_session.add(event)
        db_session.commit()
        
        # Update event_metadata
        updated_metadata = {"version": 2, "status": "published", "notes": "Updated event"}
        event.event_metadata = updated_metadata
        db_session.commit()
        
        # Verify update
        db_session.refresh(event)
        assert event.event_metadata == updated_metadata
        assert event.event_metadata["version"] == 2
        assert event.event_metadata["status"] == "published"
        assert event.event_metadata["notes"] == "Updated event"
    
    def test_event_metadata_can_be_set_to_none(self, db_session):
        """Test that event_metadata can be explicitly set to None."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        event = Events(
            user_id=user.id,
            title="Event with None Metadata",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            event_metadata=None
        )
        db_session.add(event)
        db_session.commit()
        
        # Verify event_metadata can be None
        assert event.event_metadata is None
        
        db_session.refresh(event)
        assert event.event_metadata is None
    
    def test_event_user_relationship(self, db_session):
        """Test Events-Users relationship."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        event = Events(
            user_id=user.id,
            title="Test Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1)
        )
        db_session.add(event)
        db_session.commit()
        
        # Test forward relationship
        assert event.user == user
        # Test backward relationship
        assert event in user.events
    
    def test_event_cascade_delete(self, db_session):
        """Test that events are deleted when user is deleted."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        event = Events(
            user_id=user.id,
            title="Test Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1)
        )
        db_session.add(event)
        db_session.commit()
        
        event_id = event.id
        db_session.delete(user)
        db_session.commit()
        
        # Event should be deleted
        deleted_event = db_session.get(Events, event_id)
        assert deleted_event is None


class TestInboxItemsModel:
    """Test InboxItems model CRUD operations and relationships."""
    
    def test_create_inbox_item(self, db_session):
        """Test creating a new inbox item."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        inbox_item = InboxItems(
            user_id=user.id,
            content="Test inbox content",
            category="Personal",
            priority=3,
            status="pending"
        )
        db_session.add(inbox_item)
        db_session.commit()
        
        assert inbox_item.id is not None
        assert isinstance(inbox_item.id, uuid.UUID)
        assert inbox_item.user_id == user.id
        assert inbox_item.content == "Test inbox content"
        assert inbox_item.category == "Personal"
        assert inbox_item.priority == 3
        assert inbox_item.status == "pending"
    
    def test_inbox_item_user_relationship(self, db_session):
        """Test InboxItems-Users relationship."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        inbox_item = InboxItems(
            user_id=user.id,
            content="Test content",
            priority=1,
            status="pending"
        )
        db_session.add(inbox_item)
        db_session.commit()
        
        # Test forward relationship
        assert inbox_item.user == user
        # Test backward relationship
        assert inbox_item in user.inbox_items


class TestReminderSettingsModel:
    """Test ReminderSettings model CRUD operations and relationships."""
    
    def test_create_reminder_setting(self, db_session):
        """Test creating a new reminder setting."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        event = Events(
            user_id=user.id,
            title="Test Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1)
        )
        db_session.add(event)
        db_session.commit()
        
        reminder = ReminderSettings(
            user_id=user.id,
            event_id=event.id,
            reminder_time=datetime.now() + timedelta(minutes=30),
            lead_time_minutes=15,
            reminder_type="email",
            is_active=True
        )
        db_session.add(reminder)
        db_session.commit()
        
        assert reminder.id is not None
        assert isinstance(reminder.id, uuid.UUID)
        assert reminder.user_id == user.id
        assert reminder.event_id == event.id
        assert reminder.lead_time_minutes == 15
        assert reminder.reminder_type == "email"
        assert reminder.is_active == True
    
    def test_reminder_set_null_on_event_delete(self, db_session):
        """Test that reminder event_id is set to NULL when event is deleted (SET NULL behavior)."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        event = Events(
            user_id=user.id,
            title="Test Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1)
        )
        db_session.add(event)
        db_session.commit()
        
        reminder = ReminderSettings(
            user_id=user.id,
            event_id=event.id,
            reminder_time=datetime.now(),
            lead_time_minutes=15,
            reminder_type="email"
        )
        db_session.add(reminder)
        db_session.commit()
        
        reminder_id = reminder.id
        db_session.delete(event)
        db_session.commit()
        
        # Reminder should still exist but with event_id set to None 
        # (ondelete='SET NULL' behavior)
        updated_reminder = db_session.get(ReminderSettings, reminder_id)
        assert updated_reminder is not None
        assert updated_reminder.event_id is None
    
    def test_reminder_relationships(self, db_session):
        """Test ReminderSettings relationships with User and Event."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        event = Events(
            user_id=user.id,
            title="Test Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1)
        )
        db_session.add(event)
        db_session.commit()
        
        reminder = ReminderSettings(
            user_id=user.id,
            event_id=event.id,
            reminder_time=datetime.now(),
            lead_time_minutes=15,
            reminder_type="email"
        )
        db_session.add(reminder)
        db_session.commit()
        
        # Refresh objects to ensure relationships are loaded
        db_session.refresh(reminder)
        db_session.refresh(event)
        db_session.refresh(user)
        
        # Test relationships
        assert reminder.user == user
        assert reminder.event == event
        assert reminder in user.reminder_settings
        assert reminder in event.reminder_settings


class TestAISettingsModel:
    """Test AISettings model CRUD operations and constraints."""
    
    def test_create_ai_settings(self, db_session):
        """Test creating AI settings."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        productivity_profile = {
            "focus_hours": [9, 10, 11, 14, 15],
            "break_preferences": "short_frequent",
            "notification_style": "minimal"
        }
        
        ai_settings = AISettings(
            user_id=user.id,
            productivity_profile=productivity_profile
        )
        db_session.add(ai_settings)
        db_session.commit()
        
        assert ai_settings.id is not None
        assert isinstance(ai_settings.id, uuid.UUID)
        assert ai_settings.user_id == user.id
        assert ai_settings.productivity_profile == productivity_profile
    
    def test_ai_settings_unique_user_constraint(self, db_session):
        """Test that each user can only have one AI settings record."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        ai_settings1 = AISettings(user_id=user.id, productivity_profile={"test": "data1"})
        ai_settings2 = AISettings(user_id=user.id, productivity_profile={"test": "data2"})
        
        db_session.add(ai_settings1)
        db_session.commit()
        
        db_session.add(ai_settings2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_ai_settings_user_relationship(self, db_session):
        """Test AISettings-Users relationship."""
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        ai_settings = AISettings(user_id=user.id, productivity_profile={"test": "data"})
        db_session.add(ai_settings)
        db_session.commit()
        
        # Test forward relationship
        assert ai_settings.user == user
        # Test backward relationship (one-to-one)
        assert user.ai_settings == ai_settings


class TestModelIntegration:
    """Test integration between all models."""
    
    def test_complete_user_workflow(self, db_session):
        """Test creating a user with all related models."""
        # Create user
        user = Users(username="testuser", email="test@example.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        # Create AI settings
        ai_settings = AISettings(
            user_id=user.id, 
            productivity_profile={"focus_hours": [9, 10, 11]}
        )
        db_session.add(ai_settings)
        db_session.commit()  # Commit AI settings first
        
        # Create event
        event = Events(
            user_id=user.id,
            title="Important Meeting",
            start_time=datetime.now() + timedelta(days=1),
            end_time=datetime.now() + timedelta(days=1, hours=1)
        )
        db_session.add(event)
        db_session.commit()  # Commit event before creating reminder
        
        # Create inbox item
        inbox_item = InboxItems(
            user_id=user.id,
            content="Review quarterly report",
            priority=2,
            status="pending"
        )
        db_session.add(inbox_item)
        db_session.commit()  # Commit inbox item
        
        # Create reminder - now event exists in DB
        reminder = ReminderSettings(
            user_id=user.id,
            event_id=event.id,  # event.id is now committed to DB
            reminder_time=datetime.now() + timedelta(days=1, minutes=-30),
            lead_time_minutes=30,
            reminder_type="push"
        )
        db_session.add(reminder)
        db_session.commit()
        
        # Refresh all objects to ensure relationships are loaded
        db_session.refresh(user)
        db_session.refresh(ai_settings)
        db_session.refresh(event)
        db_session.refresh(inbox_item)
        db_session.refresh(reminder)
        
        # Verify all relationships work
        assert user.ai_settings == ai_settings
        assert event in user.events
        assert inbox_item in user.inbox_items
        assert reminder in user.reminder_settings
        assert reminder.event == event
        
        # Verify cascade delete
        user_id = user.id
        ai_settings_id = ai_settings.id
        event_id = event.id
        inbox_item_id = inbox_item.id
        reminder_id = reminder.id
        
        db_session.delete(user)
        db_session.commit()
        
        # All related records should be deleted
        assert db_session.get(Users, user_id) is None
        assert db_session.get(AISettings, ai_settings_id) is None
        assert db_session.get(Events, event_id) is None
        assert db_session.get(InboxItems, inbox_item_id) is None
        assert db_session.get(ReminderSettings, reminder_id) is None