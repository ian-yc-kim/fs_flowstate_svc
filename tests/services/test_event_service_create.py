"""Unit tests for event service create_event function."""

import pytest
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException

from fs_flowstate_svc.models.flowstate_models import Users
from fs_flowstate_svc.schemas.event_schemas import EventCreate
from fs_flowstate_svc.services.event_service import create_event


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


class TestCreateEvent:
    """Test suite for create_event function."""
    
    def test_create_event_success_with_all_fields(self, db_session):
        """Test creating event with all fields including metadata."""
        user = create_user(db_session)
        
        metadata = {"priority": "high", "tags": ["important", "work"], "location": "Office"}
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        
        event_data = EventCreate(
            title="Important Meeting",
            description="Quarterly review meeting",
            start_time=start_time,
            end_time=end_time,
            category="Work",
            is_all_day=False,
            is_recurring=True,
            metadata=metadata
        )
        
        created_event = create_event(db_session, user.id, event_data)
        
        assert created_event.id is not None
        assert created_event.user_id == user.id
        assert created_event.title == "Important Meeting"
        assert created_event.description == "Quarterly review meeting"
        # Convert to UTC naive format for comparison (matches storage format)
        expected_start = start_time.astimezone(timezone.utc).replace(tzinfo=None)
        expected_end = end_time.astimezone(timezone.utc).replace(tzinfo=None)
        assert created_event.start_time == expected_start
        assert created_event.end_time == expected_end
        assert created_event.category == "Work"
        assert created_event.is_all_day is False
        assert created_event.is_recurring is True
        assert created_event.event_metadata == metadata
        assert created_event.created_at is not None
        assert created_event.updated_at is not None
    
    def test_create_event_validation_empty_title(self, db_session):
        """Test that empty title raises HTTPException 400."""
        user = create_user(db_session)
        
        event_data = EventCreate(
            title="",  # Empty title
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            end_time=datetime.now(timezone.utc) + timedelta(hours=2)
        )
        
        with pytest.raises(HTTPException) as exc_info:
            create_event(db_session, user.id, event_data)
        
        assert exc_info.value.status_code == 400
        assert "title cannot be empty" in exc_info.value.detail.lower()
    
    def test_create_event_validation_whitespace_title(self, db_session):
        """Test that whitespace-only title raises HTTPException 400."""
        user = create_user(db_session)
        
        event_data = EventCreate(
            title="   ",  # Whitespace only
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            end_time=datetime.now(timezone.utc) + timedelta(hours=2)
        )
        
        with pytest.raises(HTTPException) as exc_info:
            create_event(db_session, user.id, event_data)
        
        assert exc_info.value.status_code == 400
        assert "title cannot be empty" in exc_info.value.detail.lower()
    
    def test_create_event_validation_time_order(self, db_session):
        """Test that start_time >= end_time raises HTTPException 400."""
        user = create_user(db_session)
        
        base_time = datetime.now(timezone.utc)
        start_time = base_time + timedelta(hours=2)
        end_time = base_time + timedelta(hours=1)  # Before start_time
        
        event_data = EventCreate(
            title="Invalid Time Event",
            start_time=start_time,
            end_time=end_time
        )
        
        with pytest.raises(HTTPException) as exc_info:
            create_event(db_session, user.id, event_data)
        
        assert exc_info.value.status_code == 400
        assert "start time must be before end time" in exc_info.value.detail.lower()
    
    def test_create_event_validation_same_time(self, db_session):
        """Test that start_time == end_time raises HTTPException 400."""
        user = create_user(db_session)
        
        same_time = datetime.now(timezone.utc) + timedelta(hours=1)
        
        event_data = EventCreate(
            title="Same Time Event",
            start_time=same_time,
            end_time=same_time
        )
        
        with pytest.raises(HTTPException) as exc_info:
            create_event(db_session, user.id, event_data)
        
        assert exc_info.value.status_code == 400
        assert "start time must be before end time" in exc_info.value.detail.lower()
    
    def test_create_event_all_day_normalization(self, db_session):
        """Test that is_all_day=True normalizes times correctly."""
        user = create_user(db_session)
        
        # Provide times within the day
        start_time = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 15, 16, 45, 30, tzinfo=timezone.utc)
        
        event_data = EventCreate(
            title="All Day Event",
            start_time=start_time,
            end_time=end_time,
            is_all_day=True
        )
        
        created_event = create_event(db_session, user.id, event_data)
        
        # Should be normalized to start and end of day (converted to storage format - UTC naive)
        expected_start = datetime(2024, 1, 15, 0, 0, 0)
        expected_end = datetime(2024, 1, 15, 23, 59, 59, 999999)
        
        assert created_event.start_time == expected_start
        assert created_event.end_time == expected_end
        assert created_event.is_all_day is True
    
    def test_create_event_all_day_normalization_naive_datetime(self, db_session):
        """Test all-day normalization with naive datetime (should default to UTC)."""
        user = create_user(db_session)
        
        # Naive datetimes
        start_time = datetime(2024, 1, 15, 10, 30)
        end_time = datetime(2024, 1, 15, 16, 45)
        
        event_data = EventCreate(
            title="Naive All Day Event",
            start_time=start_time,
            end_time=end_time,
            is_all_day=True
        )
        
        created_event = create_event(db_session, user.id, event_data)
        
        # Should be normalized and treated as UTC (stored as naive)
        expected_start = datetime(2024, 1, 15, 0, 0, 0)
        expected_end = datetime(2024, 1, 15, 23, 59, 59, 999999)
        
        assert created_event.start_time == expected_start
        assert created_event.end_time == expected_end
    
    def test_conflict_detection_on_create(self, db_session):
        """Test that overlapping events raise HTTPException 409."""
        user = create_user(db_session)
        
        # Create first event
        start1 = datetime.now(timezone.utc) + timedelta(hours=1)
        end1 = start1 + timedelta(hours=2)
        
        event1_data = EventCreate(
            title="First Event",
            start_time=start1,
            end_time=end1
        )
        create_event(db_session, user.id, event1_data)
        
        # Try to create overlapping event
        start2 = start1 + timedelta(minutes=30)  # Overlaps with first event
        end2 = start2 + timedelta(hours=1)
        
        event2_data = EventCreate(
            title="Conflicting Event",
            start_time=start2,
            end_time=end2
        )
        
        with pytest.raises(HTTPException) as exc_info:
            create_event(db_session, user.id, event2_data)
        
        assert exc_info.value.status_code == 409
        assert "conflicts with existing events" in exc_info.value.detail.lower()
    
    def test_no_conflict_different_users(self, db_session):
        """Test that events from different users don't conflict."""
        user1 = create_user(db_session, "user1", "user1@example.com")
        user2 = create_user(db_session, "user2", "user2@example.com")
        
        # Create event for user1
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        
        event1_data = EventCreate(
            title="User1 Event",
            start_time=start_time,
            end_time=end_time
        )
        create_event(db_session, user1.id, event1_data)
        
        # Create overlapping event for user2 - should succeed
        event2_data = EventCreate(
            title="User2 Event",
            start_time=start_time,
            end_time=end_time
        )
        
        # Should not raise exception
        user2_event = create_event(db_session, user2.id, event2_data)
        assert user2_event.user_id == user2.id
        assert user2_event.title == "User2 Event"
    
    def test_no_conflict_non_overlapping(self, db_session):
        """Test that non-overlapping events don't conflict."""
        user = create_user(db_session)
        
        # Create first event
        start1 = datetime.now(timezone.utc) + timedelta(hours=1)
        end1 = start1 + timedelta(hours=1)
        
        event1_data = EventCreate(
            title="First Event",
            start_time=start1,
            end_time=end1
        )
        create_event(db_session, user.id, event1_data)
        
        # Create second event that starts exactly when first ends
        start2 = end1  # No overlap
        end2 = start2 + timedelta(hours=1)
        
        event2_data = EventCreate(
            title="Second Event",
            start_time=start2,
            end_time=end2
        )
        
        # Should succeed
        second_event = create_event(db_session, user.id, event2_data)
        assert second_event.title == "Second Event"
