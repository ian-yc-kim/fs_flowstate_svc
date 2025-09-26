"""Unit tests for event service delete_event function."""

import pytest
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException

from fs_flowstate_svc.models.flowstate_models import Users, ReminderSettings
from fs_flowstate_svc.schemas.event_schemas import EventCreate
from fs_flowstate_svc.services.event_service import (
    create_event,
    get_event,
    delete_event
)


def create_user(db, username="testuser", email="test@example.com"):
    """Helper function to create a test user."""
    user = Users(
        username=username,
        email=email,
        password_hash="dummy_hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_test_event(db, user_id, title="Test Event", start_hours_offset=1, duration_hours=1, **kwargs):
    """Helper function to create a test event."""
    base_time = datetime.now(timezone.utc)
    start_time = base_time + timedelta(hours=start_hours_offset)
    end_time = start_time + timedelta(hours=duration_hours)
    
    event_data = EventCreate(
        title=title,
        start_time=start_time,
        end_time=end_time,
        **kwargs
    )
    
    return create_event(db, user_id, event_data)


class TestDeleteEvent:
    """Test suite for delete_event function."""
    
    def test_delete_event_success(self, db_session):
        """Test successful event deletion."""
        user = create_user(db_session)
        event = create_test_event(db_session, user.id, "To Delete")
        event_id = event.id
        
        # Delete the event
        delete_event(db_session, event_id, user.id)
        
        # Verify event is deleted
        with pytest.raises(HTTPException) as exc_info:
            get_event(db_session, event_id, user.id)
        assert exc_info.value.status_code == 404
    
    def test_delete_event_and_reminder_nullification(self, db_session):
        """Test that deleting event nullifies linked reminder event_id."""
        user = create_user(db_session)
        event = create_test_event(db_session, user.id, "Event with Reminder")
        
        # Create reminder linked to event
        reminder = ReminderSettings(
            user_id=user.id,
            event_id=event.id,
            reminder_time=datetime.now(timezone.utc) + timedelta(minutes=30),
            lead_time_minutes=15,
            reminder_type="email"
        )
        db_session.add(reminder)
        db_session.commit()
        reminder_id = reminder.id
        
        # Delete the event
        delete_event(db_session, event.id, user.id)
        
        # Verify event is deleted
        with pytest.raises(HTTPException) as exc_info:
            get_event(db_session, event.id, user.id)
        assert exc_info.value.status_code == 404
        
        # Verify reminder still exists but event_id is None
        updated_reminder = db_session.get(ReminderSettings, reminder_id)
        assert updated_reminder is not None
        assert updated_reminder.event_id is None
        assert updated_reminder.user_id == user.id
    
    def test_delete_event_ownership_enforcement(self, db_session):
        """Test that deleting another user's event raises 403."""
        user1 = create_user(db_session, "user1", "user1@example.com")
        user2 = create_user(db_session, "user2", "user2@example.com")
        
        event = create_test_event(db_session, user1.id, "User1 Event")
        
        with pytest.raises(HTTPException) as exc_info:
            delete_event(db_session, event.id, user2.id)
        
        assert exc_info.value.status_code == 403
        assert "forbidden" in exc_info.value.detail.lower()
        
        # Verify event still exists
        still_exists = get_event(db_session, event.id, user1.id)
        assert still_exists.id == event.id
    
    def test_delete_event_nonexistent_404(self, db_session):
        """Test deleting nonexistent event raises 404."""
        user = create_user(db_session)
        random_event_id = uuid.uuid4()
        
        with pytest.raises(HTTPException) as exc_info:
            delete_event(db_session, random_event_id, user.id)
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()
    
    def test_delete_event_multiple_reminders(self, db_session):
        """Test deleting event with multiple linked reminders."""
        user = create_user(db_session)
        event = create_test_event(db_session, user.id, "Event with Multiple Reminders")
        
        # Create multiple reminders linked to event
        reminder1 = ReminderSettings(
            user_id=user.id,
            event_id=event.id,
            reminder_time=datetime.now(timezone.utc) + timedelta(minutes=30),
            lead_time_minutes=15,
            reminder_type="email"
        )
        reminder2 = ReminderSettings(
            user_id=user.id,
            event_id=event.id,
            reminder_time=datetime.now(timezone.utc) + timedelta(minutes=10),
            lead_time_minutes=5,
            reminder_type="push"
        )
        
        db_session.add(reminder1)
        db_session.add(reminder2)
        db_session.commit()
        
        reminder1_id = reminder1.id
        reminder2_id = reminder2.id
        
        # Delete the event
        delete_event(db_session, event.id, user.id)
        
        # Verify both reminders have nullified event_id
        updated_reminder1 = db_session.get(ReminderSettings, reminder1_id)
        updated_reminder2 = db_session.get(ReminderSettings, reminder2_id)
        
        assert updated_reminder1 is not None
        assert updated_reminder1.event_id is None
        assert updated_reminder2 is not None
        assert updated_reminder2.event_id is None
