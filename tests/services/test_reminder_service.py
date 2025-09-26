"""Unit tests for reminder_service functions."""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fs_flowstate_svc.models.flowstate_models import Users, UserReminderPreference
from fs_flowstate_svc.services.reminder_service import (
    _get_default_preparation_time,
    get_user_preference,
    set_user_preference,
    _calculate_basic_reminder_time
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


class TestGetDefaultPreparationTime:
    """Test suite for _get_default_preparation_time function."""
    
    @pytest.mark.parametrize("category,expected_time", [
        ("meeting", 10),
        ("deep work", 15),
        ("travel", 30),
        ("general", 5),
        ("unknown", 5),  # Should fallback to general
        ("nonexistent", 5),  # Should fallback to general
        ("random_category", 5),  # Should fallback to general
    ])
    def test_get_default_preparation_time_various_categories(self, category, expected_time):
        """Test default preparation times for various categories including unknown ones."""
        result = _get_default_preparation_time(category)
        assert result == expected_time
    
    def test_get_default_preparation_time_case_insensitive(self):
        """Test that category matching is case-insensitive."""
        # Test uppercase
        assert _get_default_preparation_time("MEETING") == 10
        assert _get_default_preparation_time("DEEP WORK") == 15
        assert _get_default_preparation_time("TRAVEL") == 30
        assert _get_default_preparation_time("GENERAL") == 5
        
        # Test mixed case
        assert _get_default_preparation_time("Meeting") == 10
        assert _get_default_preparation_time("Deep Work") == 15
        assert _get_default_preparation_time("Travel") == 30
        assert _get_default_preparation_time("General") == 5
        
        # Test lowercase
        assert _get_default_preparation_time("meeting") == 10
        assert _get_default_preparation_time("deep work") == 15
        assert _get_default_preparation_time("travel") == 30
        assert _get_default_preparation_time("general") == 5
    
    def test_get_default_preparation_time_with_spaces(self):
        """Test that categories with leading/trailing spaces are handled correctly."""
        assert _get_default_preparation_time("  meeting  ") == 10
        assert _get_default_preparation_time("\tdeep work\t") == 15
        assert _get_default_preparation_time("\n travel \n") == 30
        assert _get_default_preparation_time(" general ") == 5
        assert _get_default_preparation_time("  unknown category  ") == 5  # Fallback


class TestGetUserPreference:
    """Test suite for get_user_preference function."""
    
    def test_get_user_preference_no_existing_preference_returns_none(self, db_session):
        """Test that retrieving non-existing preference returns None."""
        user = create_test_user(db_session)
        
        result = get_user_preference(db_session, user.id, "meeting")
        
        assert result is None
    
    def test_get_user_preference_existing_preference_returns_correct_object(self, db_session):
        """Test that retrieving existing preference returns correct object."""
        user = create_test_user(db_session)
        
        # Create a preference
        preference = UserReminderPreference(
            user_id=user.id,
            event_category="meeting",
            preparation_time_minutes=20,
            is_custom=True
        )
        db_session.add(preference)
        db_session.commit()
        
        result = get_user_preference(db_session, user.id, "meeting")
        
        assert result is not None
        assert result.id == preference.id
        assert result.user_id == user.id
        assert result.event_category == "meeting"
        assert result.preparation_time_minutes == 20
        assert result.is_custom is True
    
    def test_get_user_preference_case_insensitive_category(self, db_session):
        """Test that category lookup is case-insensitive."""
        user = create_test_user(db_session)
        
        # Create preference with lowercase category
        preference = UserReminderPreference(
            user_id=user.id,
            event_category="meeting",  # lowercase in DB
            preparation_time_minutes=25,
            is_custom=False
        )
        db_session.add(preference)
        db_session.commit()
        
        # Search with different cases
        result_upper = get_user_preference(db_session, user.id, "MEETING")
        result_mixed = get_user_preference(db_session, user.id, "Meeting")
        result_spaces = get_user_preference(db_session, user.id, "  meeting  ")
        
        assert result_upper is not None
        assert result_mixed is not None
        assert result_spaces is not None
        assert result_upper.id == preference.id
        assert result_mixed.id == preference.id
        assert result_spaces.id == preference.id
    
    def test_get_user_preference_different_users(self, db_session):
        """Test that preferences are isolated between users."""
        user1 = create_test_user(db_session, "user1", "user1@example.com")
        user2 = create_test_user(db_session, "user2", "user2@example.com")
        
        # Create preference for user1
        preference1 = UserReminderPreference(
            user_id=user1.id,
            event_category="meeting",
            preparation_time_minutes=15,
            is_custom=True
        )
        db_session.add(preference1)
        db_session.commit()
        
        # user1 should find their preference
        result_user1 = get_user_preference(db_session, user1.id, "meeting")
        assert result_user1 is not None
        assert result_user1.id == preference1.id
        
        # user2 should not find user1's preference
        result_user2 = get_user_preference(db_session, user2.id, "meeting")
        assert result_user2 is None


class TestSetUserPreference:
    """Test suite for set_user_preference function."""
    
    def test_set_user_preference_creation_when_no_record_exists(self, db_session):
        """Test creating a new preference when no record exists."""
        user = create_test_user(db_session)
        
        result = set_user_preference(
            db_session, 
            user.id, 
            "meeting", 
            preparation_time_minutes=20, 
            is_custom=True
        )
        
        assert result is not None
        assert result.id is not None  # Should have an ID after commit
        assert result.user_id == user.id
        assert result.event_category == "meeting"
        assert result.preparation_time_minutes == 20
        assert result.is_custom is True
        assert result.created_at is not None
        assert result.updated_at is not None
        
        # Verify it was actually saved to the database
        saved_preference = get_user_preference(db_session, user.id, "meeting")
        assert saved_preference is not None
        assert saved_preference.id == result.id
    
    def test_set_user_preference_update_when_record_exists(self, db_session):
        """Test updating an existing preference."""
        user = create_test_user(db_session)
        
        # Create initial preference
        initial_preference = UserReminderPreference(
            user_id=user.id,
            event_category="meeting",
            preparation_time_minutes=15,
            is_custom=False
        )
        db_session.add(initial_preference)
        db_session.commit()
        initial_id = initial_preference.id
        initial_created_at = initial_preference.created_at
        
        # Update the preference
        result = set_user_preference(
            db_session,
            user.id,
            "meeting",
            preparation_time_minutes=25,
            is_custom=True
        )
        
        # Should be the same object, just updated
        assert result.id == initial_id  # Same ID
        assert result.user_id == user.id  # Same user
        assert result.event_category == "meeting"  # Same category
        assert result.preparation_time_minutes == 25  # Updated value
        assert result.is_custom is True  # Updated value
        assert result.created_at == initial_created_at  # Should remain the same
        assert result.updated_at >= initial_created_at  # Should be updated
        
        # Verify there's still only one record in DB
        all_preferences = db_session.query(UserReminderPreference).filter_by(
            user_id=user.id, event_category="meeting"
        ).all()
        assert len(all_preferences) == 1
        assert all_preferences[0].id == initial_id
    
    def test_set_user_preference_preserves_user_category_uniqueness(self, db_session):
        """Test that updating preserves unique constraint on user/category."""
        user = create_test_user(db_session)
        
        # Create two different preferences
        preference1 = set_user_preference(db_session, user.id, "meeting", 15, True)
        preference2 = set_user_preference(db_session, user.id, "travel", 30, False)
        
        # Update first preference multiple times
        updated1 = set_user_preference(db_session, user.id, "meeting", 20, False)
        updated2 = set_user_preference(db_session, user.id, "meeting", 25, True)
        
        # Should be the same object as preference1
        assert updated1.id == preference1.id
        assert updated2.id == preference1.id
        
        # Second preference should remain unchanged
        refreshed_preference2 = get_user_preference(db_session, user.id, "travel")
        assert refreshed_preference2.id == preference2.id
        assert refreshed_preference2.preparation_time_minutes == 30
        assert refreshed_preference2.is_custom is False
        
        # Should still only have two total preferences for this user
        all_user_preferences = db_session.query(UserReminderPreference).filter_by(
            user_id=user.id
        ).all()
        assert len(all_user_preferences) == 2
    
    def test_set_user_preference_case_insensitive_category(self, db_session):
        """Test that category normalization works correctly during set operations."""
        user = create_test_user(db_session)
        
        # Create with uppercase
        result1 = set_user_preference(db_session, user.id, "MEETING", 15, True)
        
        # Update with different case - should update same record
        result2 = set_user_preference(db_session, user.id, "meeting", 20, False)
        
        # Should be the same preference
        assert result1.id == result2.id
        assert result2.preparation_time_minutes == 20
        assert result2.is_custom is False
        assert result2.event_category == "meeting"  # Normalized to lowercase
        
        # Should only be one record
        all_preferences = db_session.query(UserReminderPreference).filter_by(
            user_id=user.id
        ).all()
        assert len(all_preferences) == 1
    
    def test_set_user_preference_with_spaces_in_category(self, db_session):
        """Test that categories with spaces are normalized correctly."""
        user = create_test_user(db_session)
        
        # Create with spaces
        result = set_user_preference(db_session, user.id, "  Deep Work  ", 25, True)
        
        assert result.event_category == "deep work"  # Normalized
        assert result.preparation_time_minutes == 25
        assert result.is_custom is True
        
        # Should be able to find it with different spacing
        found_preference = get_user_preference(db_session, user.id, "DEEP WORK")
        assert found_preference is not None
        assert found_preference.id == result.id
    
    def test_set_user_preference_commit_and_refresh(self, db_session):
        """Test that commit and refresh produce IDs and timestamps correctly."""
        user = create_test_user(db_session)
        
        result = set_user_preference(db_session, user.id, "meeting", 15, True)
        
        # Should have all required fields after commit/refresh
        assert result.id is not None
        assert isinstance(result.id, uuid.UUID)
        assert result.created_at is not None
        assert result.updated_at is not None
        assert isinstance(result.created_at, datetime)
        assert isinstance(result.updated_at, datetime)
        
        # Timestamps should be close to now
        now = datetime.utcnow()
        time_diff = abs((now - result.created_at).total_seconds())
        assert time_diff < 2  # Within 2 seconds


class TestCalculateBasicReminderTime:
    """Test suite for _calculate_basic_reminder_time function."""
    
    def test_calculate_basic_reminder_time_typical_scenario(self):
        """Test reminder time calculation with typical values."""
        event_start = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        preparation_time = 30
        
        result = _calculate_basic_reminder_time(event_start, preparation_time)
        
        expected = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        assert result == expected
    
    def test_calculate_basic_reminder_time_zero_minutes(self):
        """Test reminder time calculation with zero preparation time."""
        event_start = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        preparation_time = 0
        
        result = _calculate_basic_reminder_time(event_start, preparation_time)
        
        # Should be the same time
        assert result == event_start
    
    def test_calculate_basic_reminder_time_large_preparation_time(self):
        """Test reminder time calculation with large preparation time."""
        event_start = datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        preparation_time = 180  # 3 hours
        
        result = _calculate_basic_reminder_time(event_start, preparation_time)
        
        expected = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert result == expected
    
    def test_calculate_basic_reminder_time_cross_day_boundary(self):
        """Test reminder time calculation that crosses day boundary."""
        # Event starts at 1 AM
        event_start = datetime(2024, 1, 15, 1, 0, 0, tzinfo=timezone.utc)
        preparation_time = 120  # 2 hours
        
        result = _calculate_basic_reminder_time(event_start, preparation_time)
        
        # Should be 11 PM the previous day
        expected = datetime(2024, 1, 14, 23, 0, 0, tzinfo=timezone.utc)
        assert result == expected
    
    def test_calculate_basic_reminder_time_cross_month_boundary(self):
        """Test reminder time calculation that crosses month boundary."""
        # Event starts at midnight on first of month
        event_start = datetime(2024, 2, 1, 0, 30, 0, tzinfo=timezone.utc)
        preparation_time = 60  # 1 hour
        
        result = _calculate_basic_reminder_time(event_start, preparation_time)
        
        # Should be 11:30 PM on last day of previous month
        expected = datetime(2024, 1, 31, 23, 30, 0, tzinfo=timezone.utc)
        assert result == expected
    
    def test_calculate_basic_reminder_time_naive_datetime(self):
        """Test reminder time calculation with naive datetime."""
        event_start = datetime(2024, 1, 15, 14, 30, 0)  # Naive datetime
        preparation_time = 45
        
        result = _calculate_basic_reminder_time(event_start, preparation_time)
        
        expected = datetime(2024, 1, 15, 13, 45, 0)  # Also naive
        assert result == expected
        assert result.tzinfo is None  # Should remain naive
    
    def test_calculate_basic_reminder_time_different_timezones(self):
        """Test that calculation works with different timezone info."""
        # Using a different timezone (EST)
        est = timezone(timedelta(hours=-5))
        event_start = datetime(2024, 1, 15, 9, 0, 0, tzinfo=est)
        preparation_time = 30
        
        result = _calculate_basic_reminder_time(event_start, preparation_time)
        
        expected = datetime(2024, 1, 15, 8, 30, 0, tzinfo=est)
        assert result == expected
        assert result.tzinfo == est  # Should preserve timezone
    
    @pytest.mark.parametrize("prep_time,expected_hour,expected_minute", [
        (15, 13, 45),  # 15 minutes before 14:00
        (30, 13, 30),  # 30 minutes before 14:00
        (45, 13, 15),  # 45 minutes before 14:00
        (60, 13, 0),   # 1 hour before 14:00
        (90, 12, 30),  # 1.5 hours before 14:00
        (120, 12, 0),  # 2 hours before 14:00
    ])
    def test_calculate_basic_reminder_time_various_preparation_times(
        self, prep_time, expected_hour, expected_minute
    ):
        """Test reminder time calculation with various preparation times."""
        event_start = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        
        result = _calculate_basic_reminder_time(event_start, prep_time)
        
        expected = datetime(2024, 1, 15, expected_hour, expected_minute, 0, tzinfo=timezone.utc)
        assert result == expected
