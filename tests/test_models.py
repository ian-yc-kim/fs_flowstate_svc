"""Unit tests for SQLAlchemy models to verify importability, UUID generation,
timestamps, unique constraints, relationships, and cascade behaviors."""

import uuid
import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from fs_flowstate_svc.models import Base, get_db, Users, Events, InboxItems, ReminderSettings, AISettings


def test_models_import():
    """Test that all models can be imported successfully without errors."""
    # Verify all model classes are importable and have basic attributes
    assert Base is not None
    assert get_db is not None
    assert Users is not None
    assert Events is not None
    assert InboxItems is not None
    assert ReminderSettings is not None
    assert AISettings is not None
    
    # Verify models have expected table names
    assert Users.__tablename__ == 'users'
    assert Events.__tablename__ == 'events'
    assert InboxItems.__tablename__ == 'inbox_items'
    assert ReminderSettings.__tablename__ == 'reminder_settings'
    assert AISettings.__tablename__ == 'ai_settings'


def test_user_model(db_session):
    """Test Users model UUID generation, timestamps, and unique constraints."""
    # Create a user instance
    user = Users(
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password_123"
    )
    db_session.add(user)
    db_session.commit()
    
    # Assert UUID generation
    assert user.id is not None
    assert isinstance(user.id, uuid.UUID)
    
    # Assert timestamps are datetime objects and not None
    assert user.created_at is not None
    assert isinstance(user.created_at, datetime)
    assert user.updated_at is not None
    assert isinstance(user.updated_at, datetime)
    
    # Query the user back and verify data
    retrieved_user = db_session.get(Users, user.id)
    assert retrieved_user is not None
    assert retrieved_user.username == "testuser"
    assert retrieved_user.email == "test@example.com"
    assert retrieved_user.password_hash == "hashed_password_123"
    
    # Test unique constraints for username
    duplicate_username_user = Users(
        username="testuser",  # Same username
        email="different@example.com",
        password_hash="different_hash"
    )
    db_session.add(duplicate_username_user)
    with pytest.raises(IntegrityError):
        db_session.commit()
    
    # Rollback the failed transaction
    db_session.rollback()
    
    # Test unique constraints for email
    duplicate_email_user = Users(
        username="differentuser",
        email="test@example.com",  # Same email
        password_hash="different_hash"
    )
    db_session.add(duplicate_email_user)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_event_model(db_session):
    """Test Events model UUID generation, relationships, and cascade behavior."""
    # Create a user instance
    user = Users(
        username="eventuser",
        email="event@example.com",
        password_hash="hash123"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create an event instance linked to the user
    event = Events(
        user_id=user.id,
        title="Test Event",
        description="Test event description",
        start_time=datetime.now(),
        end_time=datetime.now(),
        category="Test"
    )
    db_session.add(event)
    db_session.commit()
    
    # Assert UUID generation
    assert event.id is not None
    assert isinstance(event.id, uuid.UUID)
    
    # Assert user_id matches
    assert event.user_id == user.id
    
    # Assert event.user is the correct User object
    assert event.user == user
    
    # Assert timestamps are set
    assert event.created_at is not None
    assert isinstance(event.created_at, datetime)
    assert event.updated_at is not None
    assert isinstance(event.updated_at, datetime)
    
    # Test cascade delete: delete user and verify event is also deleted
    event_id = event.id
    db_session.delete(user)
    db_session.commit()
    
    # Event should be deleted due to cascade
    deleted_event = db_session.get(Events, event_id)
    assert deleted_event is None


def test_inbox_item_model(db_session):
    """Test InboxItems model UUID generation, relationships, and cascade behavior."""
    # Create a user instance
    user = Users(
        username="inboxuser",
        email="inbox@example.com",
        password_hash="hash123"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create an inbox item instance linked to the user
    inbox_item = InboxItems(
        user_id=user.id,
        content="Test inbox content",
        category="Test",
        priority=1,
        status="pending"
    )
    db_session.add(inbox_item)
    db_session.commit()
    
    # Assert UUID generation
    assert inbox_item.id is not None
    assert isinstance(inbox_item.id, uuid.UUID)
    
    # Assert user_id matches
    assert inbox_item.user_id == user.id
    
    # Assert timestamps are set
    assert inbox_item.created_at is not None
    assert isinstance(inbox_item.created_at, datetime)
    assert inbox_item.updated_at is not None
    assert isinstance(inbox_item.updated_at, datetime)
    
    # Test cascade delete: delete user and verify inbox item is also deleted
    inbox_item_id = inbox_item.id
    db_session.delete(user)
    db_session.commit()
    
    # Inbox item should be deleted due to cascade
    deleted_inbox_item = db_session.get(InboxItems, inbox_item_id)
    assert deleted_inbox_item is None


def test_reminder_setting_model(db_session):
    """Test ReminderSettings model UUID generation, relationships, and cascade behavior."""
    # Create user and event instances
    user = Users(
        username="reminderuser",
        email="reminder@example.com",
        password_hash="hash123"
    )
    db_session.add(user)
    db_session.commit()
    
    event = Events(
        user_id=user.id,
        title="Reminder Test Event",
        start_time=datetime.now(),
        end_time=datetime.now()
    )
    db_session.add(event)
    db_session.commit()
    
    # Create a reminder settings instance linked to user and event
    reminder = ReminderSettings(
        user_id=user.id,
        event_id=event.id,
        reminder_time=datetime.now(),
        lead_time_minutes=15,
        reminder_type="email",
        is_active=True
    )
    db_session.add(reminder)
    db_session.commit()
    
    # Assert UUID generation
    assert reminder.id is not None
    assert isinstance(reminder.id, uuid.UUID)
    
    # Assert user_id and event_id match
    assert reminder.user_id == user.id
    assert reminder.event_id == event.id
    
    # Assert timestamps are set
    assert reminder.created_at is not None
    assert isinstance(reminder.created_at, datetime)
    assert reminder.updated_at is not None
    assert isinstance(reminder.updated_at, datetime)
    
    # Test ondelete='SET NULL' for event_id: delete event and verify reminder.event_id becomes None
    reminder_id = reminder.id
    db_session.delete(event)
    db_session.commit()
    
    # Reminder should still exist but with event_id set to None
    updated_reminder = db_session.get(ReminderSettings, reminder_id)
    assert updated_reminder is not None
    assert updated_reminder.event_id is None
    
    # Test cascade delete on user: delete user and verify reminder is deleted
    db_session.delete(user)
    db_session.commit()
    
    # Reminder should be deleted when user is deleted
    deleted_reminder = db_session.get(ReminderSettings, reminder_id)
    assert deleted_reminder is None


def test_ai_settings_model(db_session):
    """Test AISettings model UUID generation, JSONB storage, unique constraints, and cascade behavior."""
    # Create a user instance
    user = Users(
        username="aiuser",
        email="ai@example.com",
        password_hash="hash123"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create an AI settings instance with JSONB profile
    productivity_profile = {
        "focus_hours": [9, 10, 11, 14, 15],
        "break_preferences": "short_frequent",
        "notification_style": "minimal",
        "deep_work_blocks": 2
    }
    
    ai_settings = AISettings(
        user_id=user.id,
        productivity_profile=productivity_profile
    )
    db_session.add(ai_settings)
    db_session.commit()
    
    # Assert UUID generation
    assert ai_settings.id is not None
    assert isinstance(ai_settings.id, uuid.UUID)
    
    # Assert user_id matches
    assert ai_settings.user_id == user.id
    
    # Assert timestamps are set
    assert ai_settings.created_at is not None
    assert isinstance(ai_settings.created_at, datetime)
    assert ai_settings.updated_at is not None
    assert isinstance(ai_settings.updated_at, datetime)
    
    # Assert productivity_profile is correctly stored and retrieved as a dictionary
    assert ai_settings.productivity_profile == productivity_profile
    assert isinstance(ai_settings.productivity_profile, dict)
    assert ai_settings.productivity_profile["focus_hours"] == [9, 10, 11, 14, 15]
    assert ai_settings.productivity_profile["break_preferences"] == "short_frequent"
    
    # Test the unique constraint on user_id
    duplicate_ai_settings = AISettings(
        user_id=user.id,  # Same user_id
        productivity_profile={"different": "profile"}
    )
    db_session.add(duplicate_ai_settings)
    with pytest.raises(IntegrityError):
        db_session.commit()
    
    # Rollback the failed transaction
    db_session.rollback()
    
    # Test cascade delete: delete user and verify AI settings is also deleted
    ai_settings_id = ai_settings.id
    db_session.delete(user)
    db_session.commit()
    
    # AI settings should be deleted due to cascade
    deleted_ai_settings = db_session.get(AISettings, ai_settings_id)
    assert deleted_ai_settings is None
