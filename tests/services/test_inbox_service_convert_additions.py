"""Unit tests for convert functionality to be added to test_inbox_service.py"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from fastapi import HTTPException

from fs_flowstate_svc.models.flowstate_models import Users, InboxItems, Events
from fs_flowstate_svc.schemas import inbox_schemas, event_schemas
from fs_flowstate_svc.services import inbox_service, event_service


class TestConvertInboxItemToEvent:
    """Additional test suite for convert_inbox_item_to_event function."""
    
    def test_convert_invalid_time_order_raises_400_no_status_update(self, db_session):
        """Test conversion with invalid time order raises 400 and does not update inbox status."""
        # Create user and inbox item
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="dummy_hash"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        inbox_item = InboxItems(
            user_id=user.id,
            content="Test item",
            category="TODO",
            priority=3,
            status="PENDING"
        )
        db_session.add(inbox_item)
        db_session.commit()
        db_session.refresh(inbox_item)
        
        # Set end_time before start_time
        start_time = datetime.now(timezone.utc) + timedelta(hours=2)
        end_time = datetime.now(timezone.utc) + timedelta(hours=1)
        
        conversion_data = inbox_schemas.InboxItemConvertToEvent(
            item_id=inbox_item.id,
            start_time=start_time,
            end_time=end_time
        )
        
        with pytest.raises(HTTPException) as exc_info:
            inbox_service.convert_inbox_item_to_event(db_session, user.id, conversion_data)
        
        assert exc_info.value.status_code == 400
        assert "Event start time must be before end time" in exc_info.value.detail
        
        # Verify inbox item status remains unchanged
        db_session.refresh(inbox_item)
        assert inbox_item.status == "PENDING"
    
    def test_create_event_called_with_expected_eventcreate_payload(self, db_session, monkeypatch):
        """Test that event_service.create_event is called with correctly mapped EventCreate payload."""
        # Create user and inbox item
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="dummy_hash"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        inbox_item = InboxItems(
            user_id=user.id,
            content="Test content",
            category="TODO",
            priority=3,
            status="PENDING"
        )
        db_session.add(inbox_item)
        db_session.commit()
        db_session.refresh(inbox_item)
        
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        # Capture the EventCreate object passed to create_event
        captured_event_create = None
        original_create_event = event_service.create_event
        
        def mock_create_event(db, user_id, event_data):
            nonlocal captured_event_create
            captured_event_create = event_data
            return original_create_event(db, user_id, event_data)
        
        monkeypatch.setattr(event_service, "create_event", mock_create_event)
        
        conversion_data = inbox_schemas.InboxItemConvertToEvent(
            item_id=inbox_item.id,
            start_time=start_time,
            end_time=end_time,
            event_title="Custom Title",
            event_description="Custom Description",
            is_all_day=True,
            is_recurring=True,
            event_category="WORK",
            event_metadata={"custom": "value"}
        )
        
        created_event = inbox_service.convert_inbox_item_to_event(db_session, user.id, conversion_data)
        
        # Verify event_service.create_event was called with correct EventCreate
        assert captured_event_create is not None
        assert isinstance(captured_event_create, event_schemas.EventCreate)
        assert captured_event_create.title == "Custom Title"
        assert captured_event_create.description == "Custom Description"
        assert captured_event_create.category == "WORK"
        assert captured_event_create.is_all_day is True
        assert captured_event_create.is_recurring is True
        assert captured_event_create.metadata["custom"] == "value"
        assert captured_event_create.metadata["converted_from_inbox_item_id"] == str(inbox_item.id)
        
        # Verify inbox item status was updated
        db_session.refresh(inbox_item)
        assert inbox_item.status == inbox_schemas.InboxStatus.SCHEDULED.value
    
    def test_create_event_called_with_defaults(self, db_session, monkeypatch):
        """Test that defaults are correctly applied in EventCreate payload."""
        # Create user and inbox item
        user = Users(
            username="testuser",
            email="test@example.com",
            password_hash="dummy_hash"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        inbox_item = InboxItems(
            user_id=user.id,
            content="Short task",
            category="IDEA",
            priority=3,
            status="PENDING"
        )
        db_session.add(inbox_item)
        db_session.commit()
        db_session.refresh(inbox_item)
        
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        captured_event_create = None
        original_create_event = event_service.create_event
        
        def mock_create_event(db, user_id, event_data):
            nonlocal captured_event_create
            captured_event_create = event_data
            return original_create_event(db, user_id, event_data)
        
        monkeypatch.setattr(event_service, "create_event", mock_create_event)
        
        conversion_data = inbox_schemas.InboxItemConvertToEvent(
            item_id=inbox_item.id,
            start_time=start_time,
            end_time=end_time
            # No optional fields provided - should use defaults
        )
        
        created_event = inbox_service.convert_inbox_item_to_event(db_session, user.id, conversion_data)
        
        # Verify defaults were applied
        assert captured_event_create.title == "Short task"  # From inbox content
        assert captured_event_create.description == "Short task"  # From inbox content (short)
        assert captured_event_create.category == "IDEA"  # From inbox category
        assert captured_event_create.is_all_day is False  # Default from schema
        assert captured_event_create.is_recurring is False  # Default from schema
        assert captured_event_create.metadata["converted_from_inbox_item_id"] == str(inbox_item.id)
