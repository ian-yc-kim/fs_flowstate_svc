"""Unit tests for event service get functions."""

import pytest
import uuid
from datetime import datetime, timedelta, timezone, date, time
from fastapi import HTTPException

from fs_flowstate_svc.models.flowstate_models import Users
from fs_flowstate_svc.schemas.event_schemas import EventCreate, EventFilter
from fs_flowstate_svc.services.event_service import (
    create_event,
    get_event,
    get_events
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


class TestGetEvent:
    """Test suite for get_event function."""
    
    def test_get_event_success_and_ownership(self, db_session):
        """Test retrieving created event by id and matching user_id."""
        user = create_user(db_session)
        created_event = create_test_event(db_session, user.id, "Retrieved Event")
        
        retrieved_event = get_event(db_session, created_event.id, user.id)
        
        assert retrieved_event.id == created_event.id
        assert retrieved_event.user_id == user.id
        assert retrieved_event.title == "Retrieved Event"
    
    def test_get_event_not_found_404(self, db_session):
        """Test that random UUID returns 404."""
        user = create_user(db_session)
        random_event_id = uuid.uuid4()
        
        with pytest.raises(HTTPException) as exc_info:
            get_event(db_session, random_event_id, user.id)
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()
    
    def test_get_event_forbidden_403(self, db_session):
        """Test that accessing another user's event returns 403."""
        user1 = create_user(db_session, "user1", "user1@example.com")
        user2 = create_user(db_session, "user2", "user2@example.com")
        
        # Create event for user1
        event = create_test_event(db_session, user1.id, "User1 Event")
        
        # Try to access with user2
        with pytest.raises(HTTPException) as exc_info:
            get_event(db_session, event.id, user2.id)
        
        assert exc_info.value.status_code == 403
        assert "forbidden" in exc_info.value.detail.lower()


class TestGetEvents:
    """Test suite for get_events function."""
    
    def test_get_events_with_filters(self, db_session):
        """Test get_events with various filters."""
        user = create_user(db_session)
        
        # Create events with different dates and categories
        base_date = date(2024, 1, 15)
        
        # Event 1: Work category, Jan 15
        event1_start = datetime.combine(base_date, time(9, 0), tzinfo=timezone.utc)
        event1_data = EventCreate(
            title="Work Meeting",
            start_time=event1_start,
            end_time=event1_start + timedelta(hours=1),
            category="Work"
        )
        event1 = create_event(db_session, user.id, event1_data)
        
        # Event 2: Personal category, Jan 16
        event2_start = datetime.combine(base_date + timedelta(days=1), time(14, 0), tzinfo=timezone.utc)
        event2_data = EventCreate(
            title="Personal Appointment",
            start_time=event2_start,
            end_time=event2_start + timedelta(hours=2),
            category="Personal"
        )
        event2 = create_event(db_session, user.id, event2_data)
        
        # Event 3: Work category, Jan 17
        event3_start = datetime.combine(base_date + timedelta(days=2), time(10, 0), tzinfo=timezone.utc)
        event3_data = EventCreate(
            title="Another Work Event",
            start_time=event3_start,
            end_time=event3_start + timedelta(hours=1),
            category="Work"
        )
        event3 = create_event(db_session, user.id, event3_data)
        
        # Test no filters - should return all events
        all_events = get_events(db_session, user.id, EventFilter())
        assert len(all_events) == 3
        
        # Test filter by start_date
        filters_start = EventFilter(start_date=base_date + timedelta(days=1))
        events_from_jan16 = get_events(db_session, user.id, filters_start)
        assert len(events_from_jan16) == 2
        assert event2.id in [e.id for e in events_from_jan16]
        assert event3.id in [e.id for e in events_from_jan16]
        
        # Test filter by end_date
        filters_end = EventFilter(end_date=base_date + timedelta(days=1))
        events_until_jan16 = get_events(db_session, user.id, filters_end)
        assert len(events_until_jan16) == 2
        assert event1.id in [e.id for e in events_until_jan16]
        assert event2.id in [e.id for e in events_until_jan16]
        
        # Test filter by category
        filters_work = EventFilter(category="Work")
        work_events = get_events(db_session, user.id, filters_work)
        assert len(work_events) == 2
        assert event1.id in [e.id for e in work_events]
        assert event3.id in [e.id for e in work_events]
        
        # Test combined filters
        filters_combined = EventFilter(
            start_date=base_date,
            end_date=base_date + timedelta(days=1),
            category="Work"
        )
        combined_events = get_events(db_session, user.id, filters_combined)
        assert len(combined_events) == 1
        assert combined_events[0].id == event1.id
    
    def test_get_events_ordered_by_start_time(self, db_session):
        """Test that events are returned ordered by start_time."""
        user = create_user(db_session)
        
        base_time = datetime.now(timezone.utc)
        
        # Create events in reverse chronological order
        event3_data = EventCreate(
            title="Third Event",
            start_time=base_time + timedelta(hours=3),
            end_time=base_time + timedelta(hours=4)
        )
        event3 = create_event(db_session, user.id, event3_data)
        
        event1_data = EventCreate(
            title="First Event",
            start_time=base_time + timedelta(hours=1),
            end_time=base_time + timedelta(hours=2)
        )
        event1 = create_event(db_session, user.id, event1_data)
        
        event2_data = EventCreate(
            title="Second Event",
            start_time=base_time + timedelta(hours=2),
            end_time=base_time + timedelta(hours=3)
        )
        event2 = create_event(db_session, user.id, event2_data)
        
        # Get events - should be ordered by start_time
        events = get_events(db_session, user.id, EventFilter())
        
        assert len(events) == 3
        assert events[0].id == event1.id  # Earliest
        assert events[1].id == event2.id
        assert events[2].id == event3.id  # Latest
    
    def test_get_events_empty_for_different_user(self, db_session):
        """Test that user gets only their own events."""
        user1 = create_user(db_session, "user1", "user1@example.com")
        user2 = create_user(db_session, "user2", "user2@example.com")
        
        # Create event for user1
        create_test_event(db_session, user1.id, "User1 Event")
        
        # Get events for user2 - should be empty
        user2_events = get_events(db_session, user2.id, EventFilter())
        assert len(user2_events) == 0
