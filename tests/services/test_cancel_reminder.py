"""Unit tests for reminder cancellation functions in reminder_service."""

import pytest
import uuid
import logging
from datetime import datetime, timezone

from fs_flowstate_svc.models.flowstate_models import Users, Events, ReminderSettings
from fs_flowstate_svc.services.reminder_service import (
    cancel_scheduled_reminder,
    cancel_scheduled_reminders_for_event
)


def create_test_user(db_session, username="testuser", email="test@example.com"):
    """Helper function to create a test user."""
    user = Users(
        username=username,
        email=email,
        password_hash="dummy_hash"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_test_event(db_session, user_id, title="Test Event"):
    """Helper function to create a test event."""
    event = Events(
        user_id=user_id,
        title=title,
        start_time=datetime(2024, 1, 15, 14, 0, 0),
        end_time=datetime(2024, 1, 15, 15, 0, 0)
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


def create_test_reminder(db_session, user_id, event_id=None, status='pending'):
    """Helper function to create a test reminder."""
    reminder = ReminderSettings(
        user_id=user_id,
        event_id=event_id,
        reminder_time=datetime(2024, 1, 15, 13, 30, 0),
        lead_time_minutes=30,
        reminder_type='event',
        status=status,
        notification_method='in-app',
        is_active=True
    )
    db_session.add(reminder)
    db_session.commit()
    db_session.refresh(reminder)
    return reminder


class TestCancelScheduledReminder:
    """Test suite for cancel_scheduled_reminder function."""
    
    def test_cancel_scheduled_reminder_success(self, db_session):
        """Test successful cancellation of a pending reminder."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        reminder = create_test_reminder(db_session, user.id, event.id)
        
        result = cancel_scheduled_reminder(db_session, user.id, reminder.id)
        
        assert result is not None
        assert result.id == reminder.id
        assert result.status == 'cancelled'
        assert result.is_active is False
        assert result.user_id == user.id
        assert result.event_id == event.id
    
    def test_cancel_scheduled_reminder_not_found(self, db_session):
        """Test cancelling a non-existent reminder raises ValueError."""
        user = create_test_user(db_session)
        non_existent_id = uuid.uuid4()
        
        with pytest.raises(ValueError, match="Scheduled reminder not found or access denied"):
            cancel_scheduled_reminder(db_session, user.id, non_existent_id)
    
    def test_cancel_scheduled_reminder_wrong_user(self, db_session):
        """Test that users cannot cancel other users' reminders."""
        user1 = create_test_user(db_session, "user1", "user1@example.com")
        user2 = create_test_user(db_session, "user2", "user2@example.com")
        event = create_test_event(db_session, user1.id)
        reminder = create_test_reminder(db_session, user1.id, event.id)
        
        # user2 trying to cancel user1's reminder
        with pytest.raises(ValueError, match="Scheduled reminder not found or access denied"):
            cancel_scheduled_reminder(db_session, user2.id, reminder.id)
    
    def test_cancel_scheduled_reminder_idempotent(self, db_session):
        """Test that cancelling an already cancelled reminder is idempotent."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        reminder = create_test_reminder(db_session, user.id, event.id, status='cancelled')
        reminder.is_active = False
        db_session.commit()
        
        result = cancel_scheduled_reminder(db_session, user.id, reminder.id)
        
        # Should return the same reminder without changes
        assert result.id == reminder.id
        assert result.status == 'cancelled'
        assert result.is_active is False
    
    def test_cancel_scheduled_reminder_database_persistence(self, db_session):
        """Test that cancellation is properly persisted in database."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        reminder = create_test_reminder(db_session, user.id, event.id)
        original_created_at = reminder.created_at
        
        cancel_scheduled_reminder(db_session, user.id, reminder.id)
        
        # Fresh query to verify persistence
        fresh_reminder = db_session.query(ReminderSettings).filter_by(
            id=reminder.id
        ).first()
        
        assert fresh_reminder is not None
        assert fresh_reminder.status == 'cancelled'
        assert fresh_reminder.is_active is False
        assert fresh_reminder.created_at == original_created_at
        assert fresh_reminder.updated_at >= original_created_at
    
    def test_cancel_scheduled_reminder_without_event(self, db_session):
        """Test cancelling a reminder not associated with an event."""
        user = create_test_user(db_session)
        reminder = create_test_reminder(db_session, user.id, event_id=None)
        
        result = cancel_scheduled_reminder(db_session, user.id, reminder.id)
        
        assert result.status == 'cancelled'
        assert result.is_active is False
        assert result.event_id is None


class TestCancelScheduledRemindersForEvent:
    """Test suite for cancel_scheduled_reminders_for_event function."""
    
    def test_cancel_reminders_for_event_success(self, db_session):
        """Test successful cancellation of multiple reminders for an event."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create multiple reminders for the event
        reminder1 = create_test_reminder(db_session, user.id, event.id, 'pending')
        reminder2 = create_test_reminder(db_session, user.id, event.id, 'pending')
        reminder3 = create_test_reminder(db_session, user.id, event.id, 'failed')
        
        result = cancel_scheduled_reminders_for_event(db_session, user.id, event.id)
        
        assert len(result) == 3
        reminder_ids = [r.id for r in result]
        assert reminder1.id in reminder_ids
        assert reminder2.id in reminder_ids
        assert reminder3.id in reminder_ids
        
        # All should be cancelled
        for reminder in result:
            assert reminder.status == 'cancelled'
            assert reminder.is_active is False
    
    def test_cancel_reminders_for_event_no_reminders(self, db_session):
        """Test cancelling reminders for an event with no reminders."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        result = cancel_scheduled_reminders_for_event(db_session, user.id, event.id)
        
        assert result == []
    
    def test_cancel_reminders_for_event_excludes_already_cancelled(self, db_session):
        """Test that already cancelled reminders are not included."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create reminders with different statuses
        pending_reminder = create_test_reminder(db_session, user.id, event.id, 'pending')
        cancelled_reminder = create_test_reminder(db_session, user.id, event.id, 'cancelled')
        cancelled_reminder.is_active = False
        delivered_reminder = create_test_reminder(db_session, user.id, event.id, 'delivered')
        db_session.commit()
        
        result = cancel_scheduled_reminders_for_event(db_session, user.id, event.id)
        
        # Only the pending reminder should be cancelled
        assert len(result) == 1
        assert result[0].id == pending_reminder.id
        assert result[0].status == 'cancelled'
    
    def test_cancel_reminders_for_event_excludes_inactive(self, db_session):
        """Test that inactive reminders are not included."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create active and inactive reminders
        active_reminder = create_test_reminder(db_session, user.id, event.id, 'pending')
        inactive_reminder = create_test_reminder(db_session, user.id, event.id, 'pending')
        inactive_reminder.is_active = False
        db_session.commit()
        
        result = cancel_scheduled_reminders_for_event(db_session, user.id, event.id)
        
        # Only the active reminder should be cancelled
        assert len(result) == 1
        assert result[0].id == active_reminder.id
    
    def test_cancel_reminders_for_event_user_isolation(self, db_session):
        """Test that only the specified user's reminders are cancelled."""
        user1 = create_test_user(db_session, "user1", "user1@example.com")
        user2 = create_test_user(db_session, "user2", "user2@example.com")
        event1 = create_test_event(db_session, user1.id)
        event2 = create_test_event(db_session, user2.id)
        
        # Create reminders for both users with same event ID scenario
        reminder1 = create_test_reminder(db_session, user1.id, event1.id)
        reminder2 = create_test_reminder(db_session, user2.id, event2.id)
        
        # Cancel reminders for user1's event
        result = cancel_scheduled_reminders_for_event(db_session, user1.id, event1.id)
        
        assert len(result) == 1
        assert result[0].id == reminder1.id
        
        # user2's reminder should remain unchanged
        fresh_reminder2 = db_session.query(ReminderSettings).filter_by(
            id=reminder2.id
        ).first()
        assert fresh_reminder2.status == 'pending'
        assert fresh_reminder2.is_active is True
    
    def test_cancel_reminders_for_event_different_events(self, db_session):
        """Test that only reminders for the specified event are cancelled."""
        user = create_test_user(db_session)
        event1 = create_test_event(db_session, user.id, "Event 1")
        event2 = create_test_event(db_session, user.id, "Event 2")
        
        # Create reminders for different events
        reminder1 = create_test_reminder(db_session, user.id, event1.id)
        reminder2 = create_test_reminder(db_session, user.id, event2.id)
        
        # Cancel reminders for event1 only
        result = cancel_scheduled_reminders_for_event(db_session, user.id, event1.id)
        
        assert len(result) == 1
        assert result[0].id == reminder1.id
        
        # event2's reminder should remain unchanged
        fresh_reminder2 = db_session.query(ReminderSettings).filter_by(
            id=reminder2.id
        ).first()
        assert fresh_reminder2.status == 'pending'
        assert fresh_reminder2.is_active is True
    
    def test_cancel_reminders_for_event_database_persistence(self, db_session):
        """Test that bulk cancellation is properly persisted."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create multiple reminders
        reminder1 = create_test_reminder(db_session, user.id, event.id, 'pending')
        reminder2 = create_test_reminder(db_session, user.id, event.id, 'failed')
        
        cancel_scheduled_reminders_for_event(db_session, user.id, event.id)
        
        # Verify persistence with fresh queries
        fresh_reminder1 = db_session.query(ReminderSettings).filter_by(
            id=reminder1.id
        ).first()
        fresh_reminder2 = db_session.query(ReminderSettings).filter_by(
            id=reminder2.id
        ).first()
        
        assert fresh_reminder1.status == 'cancelled'
        assert fresh_reminder1.is_active is False
        assert fresh_reminder2.status == 'cancelled'
        assert fresh_reminder2.is_active is False
    
    def test_cancel_reminders_for_event_logging(self, db_session, caplog):
        """Test that bulk cancellation logs the correct information."""
        # Set the logging level to INFO to capture the log messages
        caplog.set_level(logging.INFO)
        
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create multiple reminders
        create_test_reminder(db_session, user.id, event.id, 'pending')
        create_test_reminder(db_session, user.id, event.id, 'failed')
        
        cancel_scheduled_reminders_for_event(db_session, user.id, event.id)
        
        # Check logging
        assert f"Cancelled 2 reminders for event {event.id}, user {user.id}" in caplog.text
