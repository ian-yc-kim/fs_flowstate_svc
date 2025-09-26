"""Unit tests for consecutive event handling in reminder_service."""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fs_flowstate_svc.models.flowstate_models import Users, Events
from fs_flowstate_svc.services.reminder_service import (
    _adjust_for_consecutive_events,
    calculate_reminder_time
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


def create_test_event(db_session, user_id, title, start_time, end_time, category="meeting", is_all_day=False):
    """Helper function to create a test event."""
    event = Events(
        user_id=user_id,
        title=title,
        start_time=start_time,
        end_time=end_time,
        category=category,
        is_all_day=is_all_day
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


class TestAdjustForConsecutiveEvents:
    """Test suite for _adjust_for_consecutive_events function."""
    
    def test_no_preceding_event(self, db_session):
        """Test that initial reminder remains unchanged when no preceding event exists."""
        user = create_test_user(db_session)
        
        # Create current event
        current_start = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        current_end = datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        current_event = create_test_event(
            db_session, user.id, "Current Event", current_start, current_end
        )
        
        # Initial reminder time
        initial_reminder = datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)
        effective_prep_time = 30
        
        result = _adjust_for_consecutive_events(
            db_session, user.id, current_event, initial_reminder, effective_prep_time
        )
        
        # Should return the initial reminder time unchanged
        assert result == initial_reminder
    
    def test_preceding_event_no_conflict(self, db_session):
        """Test that initial reminder remains unchanged when preceding event doesn't conflict."""
        user = create_test_user(db_session)
        
        # Create preceding event (ends well before initial reminder)
        preceding_start = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        preceding_end = datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
        create_test_event(
            db_session, user.id, "Preceding Event", preceding_start, preceding_end
        )
        
        # Create current event
        current_start = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        current_end = datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        current_event = create_test_event(
            db_session, user.id, "Current Event", current_start, current_end
        )
        
        # Initial reminder time (after preceding event end)
        initial_reminder = datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)
        effective_prep_time = 30
        
        result = _adjust_for_consecutive_events(
            db_session, user.id, current_event, initial_reminder, effective_prep_time
        )
        
        # Should return the initial reminder time unchanged
        assert result == initial_reminder
    
    def test_reminder_within_preceding_event_window(self, db_session):
        """Test that reminder is shifted when it falls within preceding event window."""
        user = create_test_user(db_session)
        
        # Create preceding event
        preceding_start = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        preceding_end = datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)
        create_test_event(
            db_session, user.id, "Preceding Event", preceding_start, preceding_end
        )
        
        # Create current event
        current_start = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        current_end = datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        current_event = create_test_event(db_session, user.id, "Current Event", current_start, current_end)
        
        # Initial reminder time (conflicts with preceding event)
        initial_reminder = datetime(2024, 1, 15, 13, 0, 0, tzinfo=timezone.utc)  # Within preceding event
        effective_prep_time = 60
        
        result = _adjust_for_consecutive_events(db_session, user.id, current_event, initial_reminder, effective_prep_time)
        
        # Should be adjusted to preceding end + 1 minute
        expected = datetime(2024, 1, 15, 13, 31, 0, tzinfo=timezone.utc)
        assert result == expected
    
    def test_reminder_exactly_at_preceding_event_end(self, db_session):
        """Test that reminder is shifted when it's exactly at preceding event end."""
        user = create_test_user(db_session)
        
        # Create preceding event
        preceding_start = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        preceding_end = datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)
        create_test_event(db_session, user.id, "Preceding Event", preceding_start, preceding_end)
        
        # Create current event
        current_start = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        current_end = datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        current_event = create_test_event(db_session, user.id, "Current Event", current_start, current_end)
        
        # Initial reminder time (exactly at preceding event end)
        initial_reminder = datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)
        effective_prep_time = 30
        
        result = _adjust_for_consecutive_events(db_session, user.id, current_event, initial_reminder, effective_prep_time)
        
        # Should be adjusted to preceding end + 1 minute
        expected = datetime(2024, 1, 15, 13, 31, 0, tzinfo=timezone.utc)
        assert result == expected
    
    def test_reminder_slightly_overlaps_preceding_event(self, db_session):
        """Test that reminder is shifted when it slightly overlaps preceding event."""
        user = create_test_user(db_session)
        
        # Create preceding event
        preceding_start = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        preceding_end = datetime(2024, 1, 15, 13, 45, 0, tzinfo=timezone.utc)
        create_test_event(db_session, user.id, "Preceding Event", preceding_start, preceding_end)
        
        # Create current event
        current_start = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        current_end = datetime(2024, 1, 15, 15, 30, 0, tzinfo=timezone.utc)
        current_event = create_test_event(db_session, user.id, "Current Event", current_start, current_end)
        
        # Initial reminder time (slightly before preceding event end)
        initial_reminder = datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)  # 15 minutes before preceding end
        effective_prep_time = 60
        
        result = _adjust_for_consecutive_events(db_session, user.id, current_event, initial_reminder, effective_prep_time)
        
        # Should be adjusted to preceding end + 1 minute
        expected = datetime(2024, 1, 15, 13, 46, 0, tzinfo=timezone.utc)
        assert result == expected
    
    def test_one_minute_buffer_correctly_applied(self, db_session):
        """Test that the 1-minute buffer is consistently applied."""
        user = create_test_user(db_session)
        
        # Create preceding event
        preceding_start = datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
        preceding_end = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        create_test_event(db_session, user.id, "Preceding Event", preceding_start, preceding_end)
        
        # Create current event
        current_start = datetime(2024, 1, 15, 13, 0, 0, tzinfo=timezone.utc)
        current_end = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        current_event = create_test_event(db_session, user.id, "Current Event", current_start, current_end)
        
        # Test multiple conflict scenarios to ensure buffer is always 1 minute
        test_cases = [
            # (initial_reminder, expected_result)
            (datetime(2024, 1, 15, 11, 30, 0, tzinfo=timezone.utc), datetime(2024, 1, 15, 12, 1, 0, tzinfo=timezone.utc)),  # Within preceding
            (datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc), datetime(2024, 1, 15, 12, 1, 0, tzinfo=timezone.utc)),   # Exactly at end
        ]
        
        for initial_reminder, expected in test_cases:
            result = _adjust_for_consecutive_events(db_session, user.id, current_event, initial_reminder, 60)
            assert result == expected, f"Failed for initial_reminder {initial_reminder}"
    
    def test_all_day_preceding_event(self, db_session):
        """Test behavior with all-day preceding event."""
        user = create_test_user(db_session)
        
        # Create all-day preceding event
        preceding_start = datetime(2024, 1, 14, 0, 0, 0, tzinfo=timezone.utc)  # Start of day
        preceding_end = datetime(2024, 1, 14, 23, 59, 59, 999999, tzinfo=timezone.utc)  # End of day
        create_test_event(db_session, user.id, "All-day Event", preceding_start, preceding_end, is_all_day=True)
        
        # Create current event next day
        current_start = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        current_end = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        current_event = create_test_event(db_session, user.id, "Next Day Event", current_start, current_end)
        
        # Initial reminder time that conflicts with all-day event
        initial_reminder = datetime(2024, 1, 14, 20, 0, 0, tzinfo=timezone.utc)  # 8 PM on all-day event day
        effective_prep_time = 60
        
        result = _adjust_for_consecutive_events(db_session, user.id, current_event, initial_reminder, effective_prep_time)
        
        # Should be adjusted to after all-day event + 1 minute
        # preceding_end is 2024-01-14 23:59:59.999999, so + 1 minute = 2024-01-15 00:00:59.999999
        expected = preceding_end + timedelta(minutes=1)
        assert result == expected
    
    def test_events_very_close_to_each_other(self, db_session):
        """Test handling of events that are very close to each other."""
        user = create_test_user(db_session)
        
        # Create preceding event that ends 1 minute before current event starts
        preceding_start = datetime(2024, 1, 15, 13, 0, 0, tzinfo=timezone.utc)
        preceding_end = datetime(2024, 1, 15, 13, 59, 0, tzinfo=timezone.utc)  # Ends at 13:59
        create_test_event(db_session, user.id, "Preceding Event", preceding_start, preceding_end)
        
        # Create current event that starts at 14:00
        current_start = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        current_end = datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        current_event = create_test_event(db_session, user.id, "Current Event", current_start, current_end)
        
        # Initial reminder time conflicts with preceding event
        initial_reminder = datetime(2024, 1, 15, 13, 45, 0, tzinfo=timezone.utc)
        effective_prep_time = 15
        
        result = _adjust_for_consecutive_events(db_session, user.id, current_event, initial_reminder, effective_prep_time)
        
        # Should be adjusted to preceding end + 1 minute, but capped at current event start
        # preceding end + 1 minute would be 14:00
        # current_event.start_time is stored as naive UTC in DB models; make an aware datetime for comparison
        current_event_start_aware = current_event.start_time.replace(tzinfo=timezone.utc)
        expected_candidate = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)  # preceding end + 1 minute = 14:00
        expected = min(expected_candidate, current_event_start_aware)
        assert result == expected
    
    def test_adjustment_never_after_current_event_start(self, db_session):
        """Test that final reminder time is never after current event start time."""
        user = create_test_user(db_session)
        
        # Create preceding event that ends very close to current event start
        preceding_start = datetime(2024, 1, 15, 13, 0, 0, tzinfo=timezone.utc)
        preceding_end = datetime(2024, 1, 15, 13, 59, 30, tzinfo=timezone.utc)  # 30 seconds before current start
        create_test_event(db_session, user.id, "Preceding Event", preceding_start, preceding_end)
        
        # Create current event
        current_start = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        current_end = datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        current_event = create_test_event(db_session, user.id, "Current Event", current_start, current_end)
        
        # Initial reminder time conflicts
        initial_reminder = datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)
        effective_prep_time = 30
        
        result = _adjust_for_consecutive_events(db_session, user.id, current_event, initial_reminder, effective_prep_time)
        
        # The candidate adjustment would be 14:00:30 (preceding end + 1 minute),
        # but it should be capped at current event start time (14:00:00)
        # Convert current_event.start_time to timezone-aware for comparison
        current_event_start_aware = current_event.start_time.replace(tzinfo=timezone.utc)
        assert result <= current_event_start_aware
        assert result == current_event_start_aware
    
    def test_multiple_preceding_events_chooses_immediate_predecessor(self, db_session):
        """Test that only the immediately preceding event is considered."""
        user = create_test_user(db_session)
        
        # Create multiple preceding events
        # Event 1 (earliest)
        create_test_event(
            db_session, user.id, "Event 1",
            datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
        )
        
        # Event 2 (immediate predecessor - latest ending before current)
        create_test_event(
            db_session, user.id, "Event 2",
            datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)
        )
        
        # Create current event
        current_start = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        current_end = datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        current_event = create_test_event(db_session, user.id, "Current Event", current_start, current_end)
        
        # Initial reminder time conflicts with Event 2 (immediate predecessor)
        initial_reminder = datetime(2024, 1, 15, 13, 0, 0, tzinfo=timezone.utc)
        effective_prep_time = 60
        
        result = _adjust_for_consecutive_events(db_session, user.id, current_event, initial_reminder, effective_prep_time)
        
        # Should be adjusted based on Event 2 end time (13:30), not Event 1
        expected = datetime(2024, 1, 15, 13, 31, 0, tzinfo=timezone.utc)  # Event 2 end + 1 minute
        assert result == expected
    
    def test_different_users_isolated(self, db_session):
        """Test that users' events are isolated from each other."""
        user1 = create_test_user(db_session, "user1", "user1@example.com")
        user2 = create_test_user(db_session, "user2", "user2@example.com")
        
        # Create preceding event for user1
        create_test_event(db_session, user1.id, "User1 Event",
            datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 15, 13, 30, 0, tzinfo=timezone.utc)
        )
        
        # Create current event for user2 (different user)
        current_start = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        current_end = datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        user2_current_event = create_test_event(db_session, user2.id, "User2 Event", current_start, current_end)
        
        # Initial reminder time for user2 (would conflict with user1's event if not isolated)
        initial_reminder = datetime(2024, 1, 15, 13, 0, 0, tzinfo=timezone.utc)
        effective_prep_time = 60
        
        result = _adjust_for_consecutive_events(db_session, user2.id, user2_current_event, initial_reminder, effective_prep_time)
        
        # Should return initial reminder unchanged since user2 has no preceding events
        assert result == initial_reminder


class TestCalculateReminderTime:
    """Test suite for calculate_reminder_time orchestration function."""
    
    def test_calculate_reminder_time_with_no_preceding_event(self, db_session):
        """Test calculate_reminder_time when no preceding event exists."""
        user = create_test_user(db_session)
        
        # Create event
        event_start = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        event_end = datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        event = create_test_event(db_session, user.id, "Test Event", event_start, event_end, category="meeting")
        
        result_time, result_prep_time = calculate_reminder_time(db_session, user.id, event)
        
        # Should use default meeting preparation time (10 minutes)
        expected_time = event_start - timedelta(minutes=10)
        assert result_time == expected_time
        assert result_prep_time == 10
    
    def test_calculate_reminder_time_with_preceding_event_conflict(self, db_session):
        """Test calculate_reminder_time when preceding event causes conflict."""
        user = create_test_user(db_session)
        
        # Create preceding event
        create_test_event(db_session, user.id, "Preceding Event",
            datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 15, 13, 45, 0, tzinfo=timezone.utc)
        )
        
        # Create current event
        event_start = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        event_end = datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        event = create_test_event(db_session, user.id, "Current Event", event_start, event_end, category="meeting")
        
        # Set custom user preference for longer preparation time to create conflict
        from fs_flowstate_svc.services.reminder_service import set_user_preference
        set_user_preference(db_session, user.id, "meeting", 30, True)  # 30 minutes prep time
        
        result_time, result_prep_time = calculate_reminder_time(db_session, user.id, event)
        
        # Initial would be 13:30 (14:00 - 30 minutes), which conflicts with preceding event (ends 13:45)
        # Should be adjusted to 13:46 (preceding end + 1 minute)
        expected_time = datetime(2024, 1, 15, 13, 46, 0, tzinfo=timezone.utc)
        assert result_time == expected_time
        assert result_prep_time == 30