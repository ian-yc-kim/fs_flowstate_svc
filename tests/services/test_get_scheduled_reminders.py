"""Unit tests for get_scheduled_reminders function in reminder_service."""

import pytest
from datetime import datetime, timezone, timedelta

from fs_flowstate_svc.models.flowstate_models import Users, Events, ReminderSettings
from fs_flowstate_svc.services.reminder_service import get_scheduled_reminders


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
                        reminder_time=None, status='pending', 
                        notification_method='in-app', is_active=True):
    """Helper function to create a test reminder."""
    if reminder_time is None:
        reminder_time = datetime(2024, 1, 15, 13, 30, 0)
    
    reminder = ReminderSettings(
        user_id=user_id,
        event_id=event_id,
        reminder_time=reminder_time,
        lead_time_minutes=30,
        reminder_type='event',
        status=status,
        notification_method=notification_method,
        is_active=is_active
    )
    db_session.add(reminder)
    db_session.commit()
    db_session.refresh(reminder)
    return reminder


class TestGetScheduledReminders:
    """Test suite for get_scheduled_reminders function."""
    
    def test_get_scheduled_reminders_no_filters(self, db_session):
        """Test retrieving all reminders for a user without filters."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create multiple reminders
        reminder1 = create_test_reminder(db_session, user.id, event.id)
        reminder2 = create_test_reminder(db_session, user.id, event.id, 
                                       datetime(2024, 1, 16, 10, 0, 0))
        
        result = get_scheduled_reminders(db_session, user.id)
        
        assert len(result) == 2
        reminder_ids = [r.id for r in result]
        assert reminder1.id in reminder_ids
        assert reminder2.id in reminder_ids
        
        # Should be ordered by reminder_time ascending
        assert result[0].reminder_time <= result[1].reminder_time
    
    def test_get_scheduled_reminders_empty_result(self, db_session):
        """Test retrieving reminders when none exist."""
        user = create_test_user(db_session)
        
        result = get_scheduled_reminders(db_session, user.id)
        
        assert result == []
    
    def test_get_scheduled_reminders_filter_by_event_id(self, db_session):
        """Test filtering reminders by event ID."""
        user = create_test_user(db_session)
        event1 = create_test_event(db_session, user.id, "Event 1")
        event2 = create_test_event(db_session, user.id, "Event 2")
        
        # Create reminders for different events
        reminder1 = create_test_reminder(db_session, user.id, event1.id)
        reminder2 = create_test_reminder(db_session, user.id, event2.id)
        
        # Filter by event1
        result = get_scheduled_reminders(db_session, user.id, 
                                       filters={'event_id': event1.id})
        
        assert len(result) == 1
        assert result[0].id == reminder1.id
        assert result[0].event_id == event1.id
    
    def test_get_scheduled_reminders_filter_by_status_single(self, db_session):
        """Test filtering reminders by single status."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create reminders with different statuses
        pending_reminder = create_test_reminder(db_session, user.id, event.id, status='pending')
        cancelled_reminder = create_test_reminder(db_session, user.id, event.id, status='cancelled')
        delivered_reminder = create_test_reminder(db_session, user.id, event.id, status='delivered')
        
        # Filter by pending status
        result = get_scheduled_reminders(db_session, user.id, 
                                       filters={'status': 'pending'})
        
        assert len(result) == 1
        assert result[0].id == pending_reminder.id
        assert result[0].status == 'pending'
    
    def test_get_scheduled_reminders_filter_by_status_list(self, db_session):
        """Test filtering reminders by multiple statuses."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create reminders with different statuses
        pending_reminder = create_test_reminder(db_session, user.id, event.id, status='pending')
        cancelled_reminder = create_test_reminder(db_session, user.id, event.id, status='cancelled')
        failed_reminder = create_test_reminder(db_session, user.id, event.id, status='failed')
        delivered_reminder = create_test_reminder(db_session, user.id, event.id, status='delivered')
        
        # Filter by pending and failed statuses
        result = get_scheduled_reminders(db_session, user.id, 
                                       filters={'status': ['pending', 'failed']})
        
        assert len(result) == 2
        result_ids = [r.id for r in result]
        assert pending_reminder.id in result_ids
        assert failed_reminder.id in result_ids
        assert cancelled_reminder.id not in result_ids
        assert delivered_reminder.id not in result_ids
    
    def test_get_scheduled_reminders_filter_by_time_range(self, db_session):
        """Test filtering reminders by time range."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create reminders at different times
        early_reminder = create_test_reminder(
            db_session, user.id, event.id,
            datetime(2024, 1, 10, 10, 0, 0)
        )
        middle_reminder = create_test_reminder(
            db_session, user.id, event.id,
            datetime(2024, 1, 15, 10, 0, 0)
        )
        late_reminder = create_test_reminder(
            db_session, user.id, event.id,
            datetime(2024, 1, 20, 10, 0, 0)
        )
        
        # Filter by time range (Jan 12 to Jan 18)
        start_time = datetime(2024, 1, 12, 0, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 18, 23, 59, 59, tzinfo=timezone.utc)
        
        result = get_scheduled_reminders(db_session, user.id, 
                                       filters={'time_range': (start_time, end_time)})
        
        assert len(result) == 1
        assert result[0].id == middle_reminder.id
    
    def test_get_scheduled_reminders_filter_by_notification_method(self, db_session):
        """Test filtering reminders by notification method."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create reminders with different notification methods
        in_app_reminder = create_test_reminder(db_session, user.id, event.id, 
                                              notification_method='in-app')
        email_reminder = create_test_reminder(db_session, user.id, event.id,
                                            notification_method='email')
        sms_reminder = create_test_reminder(db_session, user.id, event.id,
                                          notification_method='sms')
        
        # Filter by email notification
        result = get_scheduled_reminders(db_session, user.id, 
                                       filters={'notification_method': 'email'})
        
        assert len(result) == 1
        assert result[0].id == email_reminder.id
        assert result[0].notification_method == 'email'
    
    def test_get_scheduled_reminders_filter_by_is_active(self, db_session):
        """Test filtering reminders by active status."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create active and inactive reminders
        active_reminder = create_test_reminder(db_session, user.id, event.id, is_active=True)
        inactive_reminder = create_test_reminder(db_session, user.id, event.id, is_active=False)
        
        # Filter by active reminders
        result = get_scheduled_reminders(db_session, user.id, 
                                       filters={'is_active': True})
        
        assert len(result) == 1
        assert result[0].id == active_reminder.id
        assert result[0].is_active is True
        
        # Filter by inactive reminders
        result_inactive = get_scheduled_reminders(db_session, user.id, 
                                                filters={'is_active': False})
        
        assert len(result_inactive) == 1
        assert result_inactive[0].id == inactive_reminder.id
        assert result_inactive[0].is_active is False
    
    def test_get_scheduled_reminders_multiple_filters(self, db_session):
        """Test filtering reminders with multiple filter criteria."""
        user = create_test_user(db_session)
        event1 = create_test_event(db_session, user.id, "Event 1")
        event2 = create_test_event(db_session, user.id, "Event 2")
        
        # Create various reminders
        matching_reminder = create_test_reminder(
            db_session, user.id, event1.id,
            datetime(2024, 1, 15, 10, 0, 0),
            status='pending',
            notification_method='email',
            is_active=True
        )
        non_matching_event = create_test_reminder(
            db_session, user.id, event2.id,
            datetime(2024, 1, 15, 10, 0, 0),
            status='pending',
            notification_method='email',
            is_active=True
        )
        non_matching_status = create_test_reminder(
            db_session, user.id, event1.id,
            datetime(2024, 1, 15, 10, 0, 0),
            status='cancelled',
            notification_method='email',
            is_active=True
        )
        
        # Apply multiple filters
        filters = {
            'event_id': event1.id,
            'status': 'pending',
            'notification_method': 'email',
            'is_active': True
        }
        
        result = get_scheduled_reminders(db_session, user.id, filters=filters)
        
        assert len(result) == 1
        assert result[0].id == matching_reminder.id
    
    def test_get_scheduled_reminders_ordering(self, db_session):
        """Test that reminders are ordered by reminder_time ascending."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create reminders in non-chronological order
        reminder3 = create_test_reminder(db_session, user.id, event.id,
                                       datetime(2024, 1, 17, 10, 0, 0))
        reminder1 = create_test_reminder(db_session, user.id, event.id,
                                       datetime(2024, 1, 15, 10, 0, 0))
        reminder2 = create_test_reminder(db_session, user.id, event.id,
                                       datetime(2024, 1, 16, 10, 0, 0))
        
        result = get_scheduled_reminders(db_session, user.id)
        
        assert len(result) == 3
        # Should be ordered by reminder_time ascending
        assert result[0].id == reminder1.id
        assert result[1].id == reminder2.id
        assert result[2].id == reminder3.id
        
        # Verify actual times are in order
        assert result[0].reminder_time < result[1].reminder_time
        assert result[1].reminder_time < result[2].reminder_time
    
    def test_get_scheduled_reminders_user_isolation(self, db_session):
        """Test that users only see their own reminders."""
        user1 = create_test_user(db_session, "user1", "user1@example.com")
        user2 = create_test_user(db_session, "user2", "user2@example.com")
        event1 = create_test_event(db_session, user1.id)
        event2 = create_test_event(db_session, user2.id)
        
        # Create reminders for both users
        reminder1 = create_test_reminder(db_session, user1.id, event1.id)
        reminder2 = create_test_reminder(db_session, user2.id, event2.id)
        
        # user1 should only see their reminder
        result1 = get_scheduled_reminders(db_session, user1.id)
        assert len(result1) == 1
        assert result1[0].id == reminder1.id
        
        # user2 should only see their reminder
        result2 = get_scheduled_reminders(db_session, user2.id)
        assert len(result2) == 1
        assert result2[0].id == reminder2.id
    
    def test_get_scheduled_reminders_none_filters(self, db_session):
        """Test that None filters parameter works correctly."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        reminder = create_test_reminder(db_session, user.id, event.id)
        
        result = get_scheduled_reminders(db_session, user.id, filters=None)
        
        assert len(result) == 1
        assert result[0].id == reminder.id
    
    def test_get_scheduled_reminders_empty_filters(self, db_session):
        """Test that empty filters dictionary works correctly."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        reminder = create_test_reminder(db_session, user.id, event.id)
        
        result = get_scheduled_reminders(db_session, user.id, filters={})
        
        assert len(result) == 1
        assert result[0].id == reminder.id
    
    def test_get_scheduled_reminders_time_range_timezone_normalization(self, db_session):
        """Test that time range filters work with timezone-aware datetimes."""
        user = create_test_user(db_session)
        event = create_test_event(db_session, user.id)
        
        # Create reminder at specific time (stored as naive UTC)
        reminder = create_test_reminder(
            db_session, user.id, event.id,
            datetime(2024, 1, 15, 10, 0, 0)  # naive UTC
        )
        
        # Filter with timezone-aware times
        # 5 AM EST = 10 AM UTC, so this should match
        est = timezone(timedelta(hours=-5))
        start_time = datetime(2024, 1, 15, 4, 0, 0, tzinfo=est)  # 9 AM UTC
        end_time = datetime(2024, 1, 15, 6, 0, 0, tzinfo=est)    # 11 AM UTC
        
        result = get_scheduled_reminders(db_session, user.id,
                                       filters={'time_range': (start_time, end_time)})
        
        assert len(result) == 1
        assert result[0].id == reminder.id
