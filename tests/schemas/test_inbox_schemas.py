"""Unit tests for inbox schemas."""

import pytest
import uuid
from datetime import datetime
from pydantic import ValidationError

from fs_flowstate_svc.schemas import (
    InboxCategory,
    InboxPriority,
    InboxStatus,
    InboxItemBase,
    InboxItemCreate,
    InboxItemUpdate,
    InboxItemResponse,
    InboxItemFilter,
    InboxItemsBulkUpdate,
    InboxItemsBulkArchive,
)


class TestInboxEnums:
    """Test inbox-related enums."""
    
    def test_inbox_category_values(self):
        """Test InboxCategory enum values and types."""
        assert InboxCategory.TODO == "TODO"
        assert InboxCategory.IDEA == "IDEA"
        assert InboxCategory.NOTE == "NOTE"
        
        # Test that values are strings
        assert isinstance(InboxCategory.TODO.value, str)
        assert isinstance(InboxCategory.IDEA.value, str)
        assert isinstance(InboxCategory.NOTE.value, str)
    
    def test_inbox_priority_values(self):
        """Test InboxPriority enum values and types."""
        assert InboxPriority.P1 == 1
        assert InboxPriority.P2 == 2
        assert InboxPriority.P3 == 3
        assert InboxPriority.P4 == 4
        assert InboxPriority.P5 == 5
        
        # Test that values are integers
        assert isinstance(InboxPriority.P1.value, int)
        assert isinstance(InboxPriority.P2.value, int)
        assert isinstance(InboxPriority.P3.value, int)
        assert isinstance(InboxPriority.P4.value, int)
        assert isinstance(InboxPriority.P5.value, int)
    
    def test_inbox_status_values(self):
        """Test InboxStatus enum values and types."""
        assert InboxStatus.PENDING == "PENDING"
        assert InboxStatus.SCHEDULED == "SCHEDULED"
        assert InboxStatus.ARCHIVED == "ARCHIVED"
        assert InboxStatus.DONE == "DONE"
        
        # Test that values are strings
        assert isinstance(InboxStatus.PENDING.value, str)
        assert isinstance(InboxStatus.SCHEDULED.value, str)
        assert isinstance(InboxStatus.ARCHIVED.value, str)
        assert isinstance(InboxStatus.DONE.value, str)


class TestInboxItemBase:
    """Test InboxItemBase schema."""
    
    def test_inbox_item_base_creation(self):
        """Test successful InboxItemBase creation."""
        item = InboxItemBase(
            content="Test content",
            category=InboxCategory.TODO,
            priority=InboxPriority.P1,
            status=InboxStatus.PENDING
        )
        
        assert item.content == "Test content"
        assert item.category == InboxCategory.TODO
        assert item.priority == InboxPriority.P1
        assert item.status == InboxStatus.PENDING


class TestInboxItemCreate:
    """Test InboxItemCreate schema."""
    
    def test_inbox_item_create_with_defaults(self):
        """Test InboxItemCreate uses correct default values."""
        item = InboxItemCreate(content="Test content")
        
        assert item.content == "Test content"
        assert item.category == InboxCategory.TODO
        assert item.priority == InboxPriority.P3
        assert item.status == InboxStatus.PENDING
        
        # Verify priority default is integer 3
        assert item.priority.value == 3
    
    def test_inbox_item_create_explicit_values(self):
        """Test InboxItemCreate with explicitly provided values."""
        item = InboxItemCreate(
            content="Test content",
            category=InboxCategory.IDEA,
            priority=InboxPriority.P1,
            status=InboxStatus.SCHEDULED
        )
        
        assert item.content == "Test content"
        assert item.category == InboxCategory.IDEA
        assert item.priority == InboxPriority.P1
        assert item.status == InboxStatus.SCHEDULED
    
    def test_inbox_item_create_content_validation(self):
        """Test content field validation (min_length=1)."""
        # Valid content
        item = InboxItemCreate(content="a")
        assert item.content == "a"
        
        # Invalid empty content should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            InboxItemCreate(content="")
        
        error = exc_info.value.errors()[0]
        assert error["type"] == "string_too_short"
        assert "content" in error["loc"]


class TestInboxItemUpdate:
    """Test InboxItemUpdate schema."""
    
    def test_inbox_item_update_all_none(self):
        """Test InboxItemUpdate with all fields None."""
        item = InboxItemUpdate()
        
        assert item.content is None
        assert item.category is None
        assert item.priority is None
        assert item.status is None
    
    def test_inbox_item_update_partial_fields(self):
        """Test InboxItemUpdate with some fields provided."""
        item = InboxItemUpdate(
            content="Updated content",
            priority=InboxPriority.P5
        )
        
        assert item.content == "Updated content"
        assert item.category is None
        assert item.priority == InboxPriority.P5
        assert item.status is None
    
    def test_inbox_item_update_content_validation(self):
        """Test content validation when provided."""
        # Valid content
        item = InboxItemUpdate(content="Updated")
        assert item.content == "Updated"
        
        # None content is allowed
        item = InboxItemUpdate(content=None)
        assert item.content is None
        
        # Empty string should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            InboxItemUpdate(content="")
        
        error = exc_info.value.errors()[0]
        assert error["type"] == "string_too_short"
        assert "content" in error["loc"]


class TestInboxItemResponse:
    """Test InboxItemResponse schema."""
    
    def test_inbox_item_response_creation(self):
        """Test InboxItemResponse creation with all fields."""
        test_id = uuid.uuid4()
        test_user_id = uuid.uuid4()
        test_created_at = datetime.now()
        test_updated_at = datetime.now()
        
        item = InboxItemResponse(
            id=test_id,
            user_id=test_user_id,
            content="Test content",
            category=InboxCategory.NOTE,
            priority=InboxPriority.P2,
            status=InboxStatus.DONE,
            created_at=test_created_at,
            updated_at=test_updated_at
        )
        
        assert item.id == test_id
        assert item.user_id == test_user_id
        assert item.content == "Test content"
        assert item.category == InboxCategory.NOTE
        assert item.priority == InboxPriority.P2
        assert item.status == InboxStatus.DONE
        assert item.created_at == test_created_at
        assert item.updated_at == test_updated_at
    
    def test_inbox_item_response_from_attributes(self):
        """Test InboxItemResponse with from_attributes=True using mock ORM object."""
        # Create a mock object that simulates an ORM object
        class MockInboxItem:
            def __init__(self):
                self.id = uuid.uuid4()
                self.user_id = uuid.uuid4()
                self.content = "ORM content"
                self.category = "IDEA"
                self.priority = 4
                self.status = "ARCHIVED"
                self.created_at = datetime.now()
                self.updated_at = datetime.now()
        
        mock_orm_obj = MockInboxItem()
        
        # Should work with from_attributes=True
        item = InboxItemResponse.model_validate(mock_orm_obj)
        
        assert item.id == mock_orm_obj.id
        assert item.user_id == mock_orm_obj.user_id
        assert item.content == "ORM content"
        assert item.category == InboxCategory.IDEA
        assert item.priority == InboxPriority.P4
        assert item.status == InboxStatus.ARCHIVED
        assert item.created_at == mock_orm_obj.created_at
        assert item.updated_at == mock_orm_obj.updated_at


class TestInboxItemFilter:
    """Test InboxItemFilter schema."""
    
    def test_inbox_item_filter_all_none(self):
        """Test InboxItemFilter with all fields None."""
        filter_obj = InboxItemFilter()
        
        assert filter_obj.category is None
        assert filter_obj.priority_min is None
        assert filter_obj.priority_max is None
        assert filter_obj.status is None
    
    def test_inbox_item_filter_partial_fields(self):
        """Test InboxItemFilter with some fields provided."""
        filter_obj = InboxItemFilter(
            category=InboxCategory.TODO,
            priority_min=InboxPriority.P2,
            status=InboxStatus.PENDING
        )
        
        assert filter_obj.category == InboxCategory.TODO
        assert filter_obj.priority_min == InboxPriority.P2
        assert filter_obj.priority_max is None
        assert filter_obj.status == InboxStatus.PENDING
    
    def test_inbox_item_filter_priority_range(self):
        """Test InboxItemFilter with priority range."""
        filter_obj = InboxItemFilter(
            priority_min=InboxPriority.P1,
            priority_max=InboxPriority.P4
        )
        
        assert filter_obj.priority_min == InboxPriority.P1
        assert filter_obj.priority_max == InboxPriority.P4
        assert filter_obj.priority_min.value == 1
        assert filter_obj.priority_max.value == 4


class TestInboxItemsBulkUpdate:
    """Test InboxItemsBulkUpdate schema."""
    
    def test_inbox_items_bulk_update_creation(self):
        """Test InboxItemsBulkUpdate creation."""
        test_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
        
        bulk_update = InboxItemsBulkUpdate(
            item_ids=test_ids,
            new_status=InboxStatus.DONE
        )
        
        assert bulk_update.item_ids == test_ids
        assert bulk_update.new_status == InboxStatus.DONE
    
    def test_inbox_items_bulk_update_empty_list(self):
        """Test InboxItemsBulkUpdate with empty item_ids list."""
        bulk_update = InboxItemsBulkUpdate(
            item_ids=[],
            new_status=InboxStatus.ARCHIVED
        )
        
        assert bulk_update.item_ids == []
        assert bulk_update.new_status == InboxStatus.ARCHIVED


class TestInboxItemsBulkArchive:
    """Test InboxItemsBulkArchive schema."""
    
    def test_inbox_items_bulk_archive_creation(self):
        """Test InboxItemsBulkArchive creation."""
        test_ids = [uuid.uuid4(), uuid.uuid4()]
        
        bulk_archive = InboxItemsBulkArchive(item_ids=test_ids)
        
        assert bulk_archive.item_ids == test_ids
    
    def test_inbox_items_bulk_archive_empty_list(self):
        """Test InboxItemsBulkArchive with empty item_ids list."""
        bulk_archive = InboxItemsBulkArchive(item_ids=[])
        
        assert bulk_archive.item_ids == []


class TestSchemaImports:
    """Test that schemas can be imported from the main schemas module."""
    
    def test_import_from_schemas_module(self):
        """Test that all inbox schemas can be imported from fs_flowstate_svc.schemas."""
        # These imports should work due to __init__.py having 'from .inbox_schemas import *'
        from fs_flowstate_svc.schemas import (
            InboxCategory,
            InboxPriority,
            InboxStatus,
            InboxItemBase,
            InboxItemCreate,
            InboxItemUpdate,
            InboxItemResponse,
            InboxItemFilter,
            InboxItemsBulkUpdate,
            InboxItemsBulkArchive,
        )
        
        # Simple validation that the imports work
        assert InboxCategory.TODO == "TODO"
        assert InboxPriority.P3 == 3
        assert InboxStatus.PENDING == "PENDING"
        
        # Test that we can create instances
        create_item = InboxItemCreate(content="Test")
        assert create_item.content == "Test"
        assert create_item.category == InboxCategory.TODO
