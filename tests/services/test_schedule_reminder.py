"""Unit tests for schedule_reminder function in reminder_service."""

import pytest
import uuid
import logging
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from fs_flowstate_svc.models.flowstate_models import Users, Events, ReminderSettings
from fs_flowstate_svc.services.reminder_service import schedule_reminder


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


def create_test_event(db_session, user_id, title="Test Event", 
                     start_time=None, end_time=None):
    """Helper function to create a test event."""
    if start_time is None:
        start_time = datetime(2024, 1, 15, 14, 0, 0)
    if end_time is None:
        end_time = start_time + timedelta(hours=1)
    
    event = Events(
        user_id=user_id,
        title=title,
        start_time=start_time,
        end_time=end_time
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


class TestScheduleReminder:
    """Test suite for schedule_reminder function."""
    
    def test_schedule_reminder_basic_creation(self, db_session):
        """Test basic reminder creation with all required fields."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        reminder_time = datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)
        
        result = schedule_reminder(
            db_session,
            user.id,
            event.id,
            reminder_time,
            lead_time_minutes=30
        )
        
        assert result is not None
        assert result.id is not None
        assert result.user_id == user.id
        assert result.event_id == event.id
        # Check that reminder_time is stored in naive UTC format
        expected_time = datetime(2024, 1, 15, 13, 30, 0)  # naive UTC
        assert result.reminder_time == expected_time
        assert result.lead_time_minutes == 30
        assert result.reminder_type == 'event'
        assert result.status == 'pending'
        assert result.notification_method == 'in-app'  # default
        assert result.is_active is True
        assert result.reminder_metadata is None
        assert result.created_at is not None
        assert result.updated_at is not None
    
    def test_schedule_reminder_with_custom_notification_method(self, db_session):
        """Test reminder creation with custom notification method."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        reminder_time = datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)
        
        result = schedule_reminder(
            db_session,
            user.id,
            event.id,
            reminder_time,
            lead_time_minutes=15,
            notification_method='email'
        )
        
        assert result.notification_method == 'email'
        assert result.lead_time_minutes == 15
        assert result.status == 'pending'
    
    def test_schedule_reminder_without_event(self, db_session):
        """Test reminder creation without an associated event."""
        user = create_test_user(db_session)
        reminder_time = datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)
        
        result = schedule_reminder(
            db_session,
            user.id,
            None,  # No event
            reminder_time,
            lead_time_minutes=45
        )
        
        assert result is not None
        assert result.user_id == user.id
        assert result.event_id is None
        assert result.lead_time_minutes == 45
        assert result.status == 'pending'
    
    def test_schedule_reminder_timezone_normalization(self, db_session):
        """Test that different timezone inputs are normalized correctly."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Test with EST timezone
        est = timezone(timedelta(hours=-5))
        reminder_time_est = datetime(2024, 1, 15, 8, 30, 0, tzinfo=est)
        
        result = schedule_reminder(
            db_session,
            user.id,
            event.id,
            reminder_time_est,
            lead_time_minutes=30
        )
        
        # Should be stored as naive UTC (13:30 UTC)
        expected_time = datetime(2024, 1, 15, 13, 30, 0)  # naive UTC
        assert result.reminder_time == expected_time
    
    def test_schedule_reminder_naive_datetime(self, db_session):
        """Test reminder creation with naive datetime (assumed UTC)."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        reminder_time = datetime(2024, 1, 15, 13, 30, 0)  # naive
        
        result = schedule_reminder(db_session,
                                   user.id,
                                   event.id,
                                   reminder_time,
                                   lead_time_minutes=30)
        
        # Should be stored as naive UTC (same time)
        assert result.reminder_time == reminder_time
    
    @patch('fs_flowstate_svc.services.reminder_service.enqueue_reminder_delivery')
    def test_schedule_reminder_calls_enqueue(self, mock_enqueue, db_session):
        """Test that schedule_reminder calls the enqueue placeholder function."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        reminder_time = datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)
        
        result = schedule_reminder(
            db_session,
            user.id,
            event.id,
            reminder_time,
            lead_time_minutes=30
        )
        
        # Verify enqueue was called with the created reminder
        mock_enqueue.assert_called_once_with(result)
    
    def test_schedule_reminder_enqueue_logging(self, db_session, caplog):
        """Test that enqueue_reminder_delivery logs the reminder info."""
        # Set the logging level to INFO to capture the log messages
        caplog.set_level(logging.INFO)
        
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        reminder_time = datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)
        
        result = schedule_reminder(
            db_session,
            user.id,
            event.id,
            reminder_time,
            lead_time_minutes=30
        )
        
        # Check that enqueue logged the reminder
        assert f"Enqueued reminder delivery: id={result.id}" in caplog.text
        assert f"user_id={user.id}" in caplog.text
        assert f"event_id={event.id}" in caplog.text
    
    def test_schedule_reminder_multiple_reminders(self, db_session):
        """Test creating multiple reminders for the same user/event."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create first reminder
        reminder1 = schedule_reminder(
            db_session,
            user.id,
            event.id,
            datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc),
            lead_time_minutes=30
        )
        
        # Create second reminder with different time
        reminder2 = schedule_reminder(
            db_session,
            user.id,
            event.id,
            datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            lead_time_minutes=120
        )
        
        # Should be different reminders
        assert reminder1.id != reminder2.id
        assert reminder1.lead_time_minutes == 30
        assert reminder2.lead_time_minutes == 120
        
        # Both should exist in database
        all_reminders = db_session.query(ReminderSettings).filter_by(
            user_id=user.id, event_id=event.id
        ).all()
        assert len(all_reminders) == 2
    
    def test_schedule_reminder_different_users(self, db_session):
        """Test that reminders are properly isolated between users."""
        user1 = create_test_user(db_session, "user1", "user1@example.com")
        user2 = create_test_user(db_session, "user2", "user2@example.com")
        event1 = create_test_event(db_session, user1.id)
        event2 = create_test_event(db_session, user2.id)
        
        # Create reminders for both users
        reminder1 = schedule_reminder(db_session, user1.id, event1.id,
                                      datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc), 30)
        reminder2 = schedule_reminder(db_session, user2.id, event2.id,
                                      datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc), 30)
        
        # Should be different reminders with correct ownership
        assert reminder1.id != reminder2.id
        assert reminder1.user_id == user1.id
        assert reminder1.event_id == event1.id
        assert reminder2.user_id == user2.id
        assert reminder2.event_id == event2.id
    
    def test_schedule_reminder_database_transaction(self, db_session):
        """Test that reminder is properly committed and refreshed."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        reminder_time = datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)
        
        result = schedule_reminder(db_session, user.id, event.id, reminder_time, 30)
        
        # Verify the reminder exists in a fresh query
        fresh_reminder = db_session.query(ReminderSettings).filter_by(
            id=result.id
        ).first()
        
        assert fresh_reminder is not None
        assert fresh_reminder.id == result.id
        assert fresh_reminder.user_id == user.id
        assert fresh_reminder.event_id == event.id
        assert fresh_reminder.status == 'pending'
    
    def test_schedule_reminder_zero_lead_time(self, db_session):
        """Test reminder creation with zero lead time."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        reminder_time = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        
        result = schedule_reminder(db_session, user.id, event.id, reminder_time, 0)
        
        assert result.lead_time_minutes == 0
        assert result.status == 'pending'
    
    def test_schedule_reminder_large_lead_time(self, db_session):
        """Test reminder creation with large lead time."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        reminder_time = datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)
        
        result = schedule_reminder(db_session, user.id, event.id, reminder_time, 1440)  # 24 hours
        
        assert result.lead_time_minutes == 1440
        assert result.status == 'pending'
