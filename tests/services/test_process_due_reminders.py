"""Unit tests for process_due_reminders function in reminder_service."""

import pytest
import logging
from datetime import datetime, timezone, timedelta

from fs_flowstate_svc.models.flowstate_models import Users, Events, ReminderSettings
from fs_flowstate_svc.services.reminder_service import process_due_reminders


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


def create_test_reminder(db_session, user_id, event_id=None, 
                        reminder_time=None, status='pending'):
    """Helper function to create a test reminder."""
    if reminder_time is None:
        reminder_time = datetime.utcnow() - timedelta(minutes=10)  # Due 10 minutes ago
    
    reminder = ReminderSettings(
        user_id=user_id,
        event_id=event_id,
        reminder_time=reminder_time,
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


class TestProcessDueReminders:
    """Test suite for process_due_reminders function."""
    
    def test_process_due_reminders_finds_due_reminders(self, db_session):
        """Test that process_due_reminders finds pending reminders that are due."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create a reminder that's due (10 minutes ago)
        past_time = datetime.utcnow() - timedelta(minutes=10)
        due_reminder = create_test_reminder(db_session, user.id, event.id, 
                                          past_time, 'pending')
        
        result = process_due_reminders(db_session)
        
        assert len(result) == 1
        assert result[0].id == due_reminder.id
        assert result[0].status == 'pending'
        assert result[0].reminder_time <= datetime.utcnow()
    
    def test_process_due_reminders_ignores_future_reminders(self, db_session):
        """Test that future reminders are not included in results."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create reminders: one due, one future
        past_time = datetime.utcnow() - timedelta(minutes=10)
        future_time = datetime.utcnow() + timedelta(minutes=10)
        
        due_reminder = create_test_reminder(db_session, user.id, event.id, 
                                          past_time, 'pending')
        future_reminder = create_test_reminder(db_session, user.id, event.id, 
                                             future_time, 'pending')
        
        result = process_due_reminders(db_session)
        
        assert len(result) == 1
        assert result[0].id == due_reminder.id
        
        # Verify future reminder is not included
        result_ids = [r.id for r in result]
        assert future_reminder.id not in result_ids
    
    def test_process_due_reminders_ignores_non_pending_status(self, db_session):
        """Test that non-pending reminders are not included."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        past_time = datetime.utcnow() - timedelta(minutes=10)
        
        # Create reminders with different statuses
        pending_reminder = create_test_reminder(db_session, user.id, event.id, 
                                              past_time, 'pending')
        cancelled_reminder = create_test_reminder(db_session, user.id, event.id, 
                                                past_time, 'cancelled')
        delivered_reminder = create_test_reminder(db_session, user.id, event.id, 
                                                past_time, 'delivered')
        failed_reminder = create_test_reminder(db_session, user.id, event.id, 
                                             past_time, 'failed')
        
        result = process_due_reminders(db_session)
        
        assert len(result) == 1
        assert result[0].id == pending_reminder.id
        assert result[0].status == 'pending'
    
    def test_process_due_reminders_empty_result(self, db_session):
        """Test that empty result is returned when no due reminders exist."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create only future reminders
        future_time = datetime.utcnow() + timedelta(hours=1)
        create_test_reminder(db_session, user.id, event.id, future_time, 'pending')
        
        result = process_due_reminders(db_session)
        
        assert result == []
    
    def test_process_due_reminders_multiple_users(self, db_session):
        """Test that due reminders from multiple users are all found."""
        user1 = create_test_user(db_session, "user1", "user1@example.com")
        user2 = create_test_user(db_session, "user2", "user2@example.com")
        event1 = create_test_event(db_session, user1.id)
        event2 = create_test_event(db_session, user2.id)
        past_time = datetime.utcnow() - timedelta(minutes=10)
        
        # Create due reminders for both users
        reminder1 = create_test_reminder(db_session, user1.id, event1.id, 
                                       past_time, 'pending')
        reminder2 = create_test_reminder(db_session, user2.id, event2.id, 
                                       past_time, 'pending')
        
        result = process_due_reminders(db_session)
        
        assert len(result) == 2
        result_ids = [r.id for r in result]
        assert reminder1.id in result_ids
        assert reminder2.id in result_ids
    
    def test_process_due_reminders_without_events(self, db_session):
        """Test processing reminders that are not associated with events."""
        user = create_test_user(db_session)
        past_time = datetime.utcnow() - timedelta(minutes=10)
        
        # Create reminder without event
        reminder = create_test_reminder(db_session, user.id, event_id=None, 
                                      reminder_time=past_time, status='pending')
        
        result = process_due_reminders(db_session)
        
        assert len(result) == 1
        assert result[0].id == reminder.id
        assert result[0].event_id is None
    
    def test_process_due_reminders_logging(self, db_session, caplog):
        """Test that due reminders are logged correctly."""
        # Set the logging level to INFO to capture the log messages
        caplog.set_level(logging.INFO)
        
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        past_time = datetime.utcnow() - timedelta(minutes=10)
        
        # Create multiple due reminders
        reminder1 = create_test_reminder(db_session, user.id, event.id, 
                                       past_time, 'pending')
        reminder2 = create_test_reminder(db_session, user.id, None, 
                                       past_time, 'pending')
        
        process_due_reminders(db_session)
        
        # Check that individual reminders are logged
        assert f"Due reminder found: id={reminder1.id}" in caplog.text
        assert f"user_id={user.id}" in caplog.text
        assert f"event_id={event.id}" in caplog.text
        
        assert f"Due reminder found: id={reminder2.id}" in caplog.text
        assert f"event_id=None" in caplog.text
        
        # Check summary logging
        assert "Found 2 due reminders" in caplog.text
    
    def test_process_due_reminders_no_due_reminders_logging(self, db_session, caplog):
        """Test logging when no due reminders are found."""
        # Set the logging level to INFO to capture the log messages
        caplog.set_level(logging.INFO)
        
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        future_time = datetime.utcnow() + timedelta(hours=1)
        
        # Create only future reminders
        create_test_reminder(db_session, user.id, event.id, future_time, 'pending')
        
        process_due_reminders(db_session)
        
        # Should log that 0 due reminders were found
        assert "Found 0 due reminders" in caplog.text
    
    def test_process_due_reminders_exact_due_time(self, db_session):
        """Test reminder that is due exactly now."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create reminder due 1 second ago to avoid timing issues
        past_time = datetime.utcnow() - timedelta(seconds=1)
        reminder = create_test_reminder(db_session, user.id, event.id, 
                                      past_time, 'pending')
        
        result = process_due_reminders(db_session)
        
        assert len(result) >= 1
        reminder_ids = [r.id for r in result]
        assert reminder.id in reminder_ids
    
    def test_process_due_reminders_does_not_modify_reminders(self, db_session):
        """Test that process_due_reminders does not modify reminder records."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        past_time = datetime.utcnow() - timedelta(minutes=10)
        
        reminder = create_test_reminder(db_session, user.id, event.id, 
                                      past_time, 'pending')
        original_status = reminder.status
        original_updated_at = reminder.updated_at
        
        process_due_reminders(db_session)
        
        # Refresh to get current state
        db_session.refresh(reminder)
        
        # Should not have modified the reminder
        assert reminder.status == original_status
        assert reminder.updated_at == original_updated_at
        assert reminder.is_active is True
    
    def test_process_due_reminders_with_various_lead_times(self, db_session):
        """Test that reminders with different lead times are processed correctly."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        past_time = datetime.utcnow() - timedelta(minutes=10)
        
        # Create reminders with different lead times
        reminder1 = ReminderSettings(
            user_id=user.id,
            event_id=event.id,
            reminder_time=past_time,
            lead_time_minutes=15,
            reminder_type='event',
            status='pending',
            notification_method='in-app',
            is_active=True
        )
        reminder2 = ReminderSettings(
            user_id=user.id,
            event_id=event.id,
            reminder_time=past_time,
            lead_time_minutes=60,
            reminder_type='event',
            status='pending',
            notification_method='email',
            is_active=True
        )
        
        db_session.add_all([reminder1, reminder2])
        db_session.commit()
        
        result = process_due_reminders(db_session)
        
        assert len(result) == 2
        result_ids = [r.id for r in result]
        assert reminder1.id in result_ids
        assert reminder2.id in result_ids
