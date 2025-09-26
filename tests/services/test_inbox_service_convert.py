"""Unit tests for inbox service convert_inbox_item_to_event function."""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException

from fs_flowstate_svc.models.flowstate_models import Users, InboxItems, Events
from fs_flowstate_svc.schemas import inbox_schemas, event_schemas
from fs_flowstate_svc.services import inbox_service, event_service


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


def create_inbox_item(db, user, content="Test content", category="TODO", priority=3, status="PENDING"):
    """Helper function to create an inbox item directly in database."""
    item = InboxItems(
        user_id=user.id,
        content=content,
        category=category,
        priority=priority,
        status=status
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def create_event(db, user, start_time, end_time, title="Test Event"):
    """Helper function to create an event directly in database."""
    event = Events(
        user_id=user.id,
        title=title,
        start_time=start_time,
        end_time=end_time
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


class TestConvertInboxItemToEvent:
    """Test suite for convert_inbox_item_to_event function."""
    
    def test_convert_success_creates_event_and_updates_status(self, db_session):
        """Test successful conversion creates event and updates inbox item status to SCHEDULED."""
        user = create_user(db_session)
        inbox_item = create_inbox_item(db_session, user, content="Meeting with client", category="TODO")
        
        # Set up conversion data
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        conversion_data = inbox_schemas.InboxItemConvertToEvent(
            item_id=inbox_item.id,
            start_time=start_time,
            end_time=end_time,
            event_title="Client Meeting",
            event_description="Important client discussion",
            is_all_day=False,
            is_recurring=False,
            event_category="WORK",
            event_metadata={"priority": "high"}
        )
        
        # Execute conversion
        created_event = inbox_service.convert_inbox_item_to_event(db_session, user.id, conversion_data)
        
        # Verify event was created with correct properties
        assert created_event is not None
        assert isinstance(created_event, Events)
        assert created_event.user_id == user.id
        assert created_event.title == "Client Meeting"
        assert created_event.description == "Important client discussion"
        assert created_event.category == "WORK"
        assert created_event.is_all_day is False
        assert created_event.is_recurring is False
        
        # Verify metadata includes original inbox item ID
        assert created_event.event_metadata is not None
        assert created_event.event_metadata["priority"] == "high"
        assert created_event.event_metadata["converted_from_inbox_item_id"] == str(inbox_item.id)
        
        # Verify inbox item status was updated to SCHEDULED
        db_session.refresh(inbox_item)
        assert inbox_item.status == inbox_schemas.InboxStatus.SCHEDULED.value
    
    def test_convert_not_owned_or_missing_item_raises_404(self, db_session):
        """Test conversion fails with 404 for non-existent or unowned items."""
        user1 = create_user(db_session, "user1", "user1@example.com")
        user2 = create_user(db_session, "user2", "user2@example.com")
        
        # Test with non-existent item ID
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        random_item_id = uuid.uuid4()
        conversion_data = inbox_schemas.InboxItemConvertToEvent(
            item_id=random_item_id,
            start_time=start_time,
            end_time=end_time
        )
        
        with pytest.raises(HTTPException) as exc_info:
            inbox_service.convert_inbox_item_to_event(db_session, user1.id, conversion_data)
        
        assert exc_info.value.status_code == 404
        assert "Inbox item not found or not owned" in exc_info.value.detail
        
        # Test with another user's item
        user2_item = create_inbox_item(db_session, user2, content="User 2 item")
        
        conversion_data_other_user = inbox_schemas.InboxItemConvertToEvent(
            item_id=user2_item.id,
            start_time=start_time,
            end_time=end_time
        )
        
        with pytest.raises(HTTPException) as exc_info:
            inbox_service.convert_inbox_item_to_event(db_session, user1.id, conversion_data_other_user)
        
        assert exc_info.value.status_code == 404
        assert "Inbox item not found or not owned" in exc_info.value.detail
        
        # Verify original inbox item status remains unchanged
        db_session.refresh(user2_item)
        assert user2_item.status == "PENDING"
    
    def test_convert_conflict_raises_409_and_does_not_update_status(self, db_session):
        """Test conversion fails with 409 when event times conflict and does not update status."""
        user = create_user(db_session)
        inbox_item = create_inbox_item(db_session, user, content="New meeting")
        
        # Create existing event that will conflict
        conflict_start = datetime.now(timezone.utc) + timedelta(hours=1)
        conflict_end = conflict_start + timedelta(hours=2)
        existing_event = create_event(db_session, user, conflict_start, conflict_end, "Existing Event")
        
        # Try to convert inbox item with overlapping times
        conversion_data = inbox_schemas.InboxItemConvertToEvent(
            item_id=inbox_item.id,
            start_time=conflict_start + timedelta(minutes=30),  # Overlaps with existing event
            end_time=conflict_end + timedelta(minutes=30)
        )
        
        with pytest.raises(HTTPException) as exc_info:
            inbox_service.convert_inbox_item_to_event(db_session, user.id, conversion_data)
        
        assert exc_info.value.status_code == 409
        assert "Event time conflicts with existing events" in exc_info.value.detail
        
        # Verify inbox item status remains unchanged
        db_session.refresh(inbox_item)
        assert inbox_item.status == "PENDING"
    
    def test_default_title_and_description_logic(self, db_session):
        """Test default title and description logic when not provided."""
        user = create_user(db_session)
        
        # Test with short content - should be used for both title and description
        short_content = "Short task"
        inbox_item_short = create_inbox_item(db_session, user, content=short_content, category="IDEA")
        
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        conversion_data_short = inbox_schemas.InboxItemConvertToEvent(
            item_id=inbox_item_short.id,
            start_time=start_time,
            end_time=end_time
            # No event_title or event_description provided
        )
        
        created_event_short = inbox_service.convert_inbox_item_to_event(db_session, user.id, conversion_data_short)
        
        # Should use content for both title and description
        assert created_event_short.title == short_content
        assert created_event_short.description == short_content
        # Should use inbox item category as event category
        assert created_event_short.category == "IDEA"
        
        # Test with long content - should be used for title but not description
        long_content = "This is a very long content that exceeds 255 characters. " * 10  # Over 255 chars
        inbox_item_long = create_inbox_item(db_session, user, content=long_content)
        
        start_time2 = datetime.now(timezone.utc) + timedelta(hours=3)
        end_time2 = start_time2 + timedelta(hours=1)
        
        conversion_data_long = inbox_schemas.InboxItemConvertToEvent(
            item_id=inbox_item_long.id,
            start_time=start_time2,
            end_time=end_time2
        )
        
        created_event_long = inbox_service.convert_inbox_item_to_event(db_session, user.id, conversion_data_long)
        
        # Title should be truncated to 255 chars
        assert len(created_event_long.title) <= 255
        assert created_event_long.title == long_content.strip()[:255]
        # Description should be empty for long content
        assert created_event_long.description == ""
    
    def test_convert_with_partial_optional_fields(self, db_session):
        """Test conversion with some optional fields provided."""
        user = create_user(db_session)
        inbox_item = create_inbox_item(db_session, user, content="Test task", category="NOTE")
        
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        
        # Provide only event_title, let other fields use defaults
        conversion_data = inbox_schemas.InboxItemConvertToEvent(
            item_id=inbox_item.id,
            start_time=start_time,
            end_time=end_time,
            event_title="Custom Title",
            is_all_day=True
            # event_description, event_category, event_metadata not provided
        )
        
        created_event = inbox_service.convert_inbox_item_to_event(db_session, user.id, conversion_data)
        
        assert created_event.title == "Custom Title"
        assert created_event.description == "Test task"  # Short content used as description
        assert created_event.category == "NOTE"  # From inbox item
        assert created_event.is_all_day is True
        assert created_event.is_recurring is False  # Default
        
        # Metadata should only contain the inbox item ID
        assert created_event.event_metadata["converted_from_inbox_item_id"] == str(inbox_item.id)
        assert len(created_event.event_metadata) == 1
    
    def test_convert_preserves_existing_metadata_and_adds_inbox_id(self, db_session):
        """Test that conversion preserves existing metadata and adds inbox item ID."""
        user = create_user(db_session)
        inbox_item = create_inbox_item(db_session, user, content="Important task")
        
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        existing_metadata = {
            "priority": "high",
            "project": "client-work",
            "tags": ["urgent", "important"]
        }
        
        conversion_data = inbox_schemas.InboxItemConvertToEvent(
            item_id=inbox_item.id,
            start_time=start_time,
            end_time=end_time,
            event_metadata=existing_metadata
        )
        
        created_event = inbox_service.convert_inbox_item_to_event(db_session, user.id, conversion_data)
        
        # Should preserve existing metadata
        assert created_event.event_metadata["priority"] == "high"
        assert created_event.event_metadata["project"] == "client-work"
        assert created_event.event_metadata["tags"] == ["urgent", "important"]
        
        # Should add inbox item ID
        assert created_event.event_metadata["converted_from_inbox_item_id"] == str(inbox_item.id)
    
    def test_convert_with_none_metadata_creates_empty_dict_with_inbox_id(self, db_session):
        """Test that None metadata is handled correctly."""
        user = create_user(db_session)
        inbox_item = create_inbox_item(db_session, user, content="Simple task")
        
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        conversion_data = inbox_schemas.InboxItemConvertToEvent(
            item_id=inbox_item.id,
            start_time=start_time,
            end_time=end_time,
            event_metadata=None
        )
        
        created_event = inbox_service.convert_inbox_item_to_event(db_session, user.id, conversion_data)
        
        # Should create dict with only inbox item ID
        assert isinstance(created_event.event_metadata, dict)
        assert created_event.event_metadata["converted_from_inbox_item_id"] == str(inbox_item.id)
        assert len(created_event.event_metadata) == 1
