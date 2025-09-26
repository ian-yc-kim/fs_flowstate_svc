"""Unit tests for event service update_event function."""

import pytest
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException

from fs_flowstate_svc.models.flowstate_models import Users
from fs_flowstate_svc.schemas.event_schemas import EventCreate, EventUpdate
from fs_flowstate_svc.services.event_service import (
    create_event,
    get_event,
    update_event
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


class TestUpdateEvent:
    """Test suite for update_event function."""
    
    def test_update_event_success(self, db_session):
        """Test successful event update with various fields."""
        user = create_user(db_session)
        original_event = create_test_event(
            db_session, user.id, "Original Event", 
            description="Original description", category="Work"
        )
        
        new_metadata = {"updated": True, "priority": "high"}
        update_data = EventUpdate(
            title="Updated Event",
            description="Updated description",
            category="Personal",
            is_recurring=True,
            metadata=new_metadata
        )
        
        updated_event = update_event(db_session, original_event.id, user.id, update_data)
        
        assert updated_event.id == original_event.id
        assert updated_event.title == "Updated Event"
        assert updated_event.description == "Updated description"
        assert updated_event.category == "Personal"
        assert updated_event.is_recurring is True
        assert updated_event.event_metadata == new_metadata
        # Original values should be preserved if not updated
        assert updated_event.start_time == original_event.start_time
        assert updated_event.end_time == original_event.end_time
    
    def test_update_event_time_fields(self, db_session):
        """Test updating start_time and end_time."""
        user = create_user(db_session)
        original_event = create_test_event(db_session, user.id)
        
        new_start = datetime.now(timezone.utc) + timedelta(hours=5)
        new_end = new_start + timedelta(hours=3)
        
        update_data = EventUpdate(
            start_time=new_start,
            end_time=new_end
        )
        
        updated_event = update_event(db_session, original_event.id, user.id, update_data)
        
        # Compare with storage format (UTC naive)
        expected_start = new_start.astimezone(timezone.utc).replace(tzinfo=None)
        expected_end = new_end.astimezone(timezone.utc).replace(tzinfo=None)
        assert updated_event.start_time == expected_start
        assert updated_event.end_time == expected_end
    
    def test_update_event_toggle_all_day(self, db_session):
        """Test toggling is_all_day flag and time normalization."""
        user = create_user(db_session)
        
        # Create regular event
        start_time = datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 15, 16, 45, tzinfo=timezone.utc)
        
        event_data = EventCreate(
            title="Regular Event",
            start_time=start_time,
            end_time=end_time,
            is_all_day=False
        )
        event = create_event(db_session, user.id, event_data)
        
        # Update to all-day event
        update_data = EventUpdate(is_all_day=True)
        updated_event = update_event(db_session, event.id, user.id, update_data)
        
        # Times should be normalized (stored as UTC naive)
        expected_start = datetime(2024, 1, 15, 0, 0, 0)
        expected_end = datetime(2024, 1, 15, 23, 59, 59, 999999)
        
        assert updated_event.is_all_day is True
        assert updated_event.start_time == expected_start
        assert updated_event.end_time == expected_end
    
    def test_update_event_validation_empty_title(self, db_session):
        """Test that updating to empty title raises HTTPException 400."""
        user = create_user(db_session)
        event = create_test_event(db_session, user.id)
        
        update_data = EventUpdate(title="")
        
        with pytest.raises(HTTPException) as exc_info:
            update_event(db_session, event.id, user.id, update_data)
        
        assert exc_info.value.status_code == 400
        assert "title cannot be empty" in exc_info.value.detail.lower()
    
    def test_update_event_validation_time_order(self, db_session):
        """Test that invalid time order in update raises HTTPException 400."""
        user = create_user(db_session)
        event = create_test_event(db_session, user.id)
        
        base_time = datetime.now(timezone.utc)
        # Invalid: start after end
        update_data = EventUpdate(
            start_time=base_time + timedelta(hours=2),
            end_time=base_time + timedelta(hours=1)
        )
        
        with pytest.raises(HTTPException) as exc_info:
            update_event(db_session, event.id, user.id, update_data)
        
        assert exc_info.value.status_code == 400
        assert "start time must be before end time" in exc_info.value.detail.lower()
    
    def test_update_event_conflict_created(self, db_session):
        """Test that updating to overlapping time raises HTTPException 409."""
        user = create_user(db_session)
        
        # Create two non-overlapping events
        event1 = create_test_event(db_session, user.id, "Event 1", start_hours_offset=1, duration_hours=1)
        event2 = create_test_event(db_session, user.id, "Event 2", start_hours_offset=3, duration_hours=1)
        
        # Convert event1 times to timezone-aware for calculation
        event1_start = datetime.fromtimestamp(event1.start_time.timestamp(), tz=timezone.utc)
        
        # Update event2 to overlap with event1
        conflicting_start = event1_start + timedelta(minutes=30)
        conflicting_end = conflicting_start + timedelta(hours=1)
        
        update_data = EventUpdate(
            start_time=conflicting_start,
            end_time=conflicting_end
        )
        
        with pytest.raises(HTTPException) as exc_info:
            update_event(db_session, event2.id, user.id, update_data)
        
        assert exc_info.value.status_code == 409
        assert "conflicts with existing events" in exc_info.value.detail.lower()
    
    def test_update_event_resolve_conflict(self, db_session):
        """Test updating to non-overlapping time after conflict setup."""
        user = create_user(db_session)
        
        # Create two events
        event1 = create_test_event(db_session, user.id, "Event 1", start_hours_offset=1)
        event2 = create_test_event(db_session, user.id, "Event 2", start_hours_offset=5)
        
        # Convert event1 times to timezone-aware for calculation
        event1_end = datetime.fromtimestamp(event1.end_time.timestamp(), tz=timezone.utc)
        
        # Move event2 to non-overlapping time - should succeed
        new_start = event1_end + timedelta(hours=1)
        new_end = new_start + timedelta(hours=1)
        
        update_data = EventUpdate(
            start_time=new_start,
            end_time=new_end
        )
        
        updated_event = update_event(db_session, event2.id, user.id, update_data)
        expected_start = new_start.astimezone(timezone.utc).replace(tzinfo=None)
        expected_end = new_end.astimezone(timezone.utc).replace(tzinfo=None)
        assert updated_event.start_time == expected_start
        assert updated_event.end_time == expected_end
    
    def test_update_event_ownership_enforcement(self, db_session):
        """Test that updating another user's event raises 403."""
        user1 = create_user(db_session, "user1", "user1@example.com")
        user2 = create_user(db_session, "user2", "user2@example.com")
        
        event = create_test_event(db_session, user1.id, "User1 Event")
        
        update_data = EventUpdate(title="Hacked Event")
        
        with pytest.raises(HTTPException) as exc_info:
            update_event(db_session, event.id, user2.id, update_data)
        
        assert exc_info.value.status_code == 403
        assert "forbidden" in exc_info.value.detail.lower()
    
    def test_update_event_nonexistent_404(self, db_session):
        """Test updating nonexistent event raises 404."""
        user = create_user(db_session)
        random_event_id = uuid.uuid4()
        
        update_data = EventUpdate(title="New Title")
        
        with pytest.raises(HTTPException) as exc_info:
            update_event(db_session, random_event_id, user.id, update_data)
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()
