"""Unit tests for inbox service CRUD operations, filtering, and bulk operations."""

import pytest
import uuid
from typing import List
from fastapi import HTTPException

from fs_flowstate_svc.models.flowstate_models import Users, InboxItems
from fs_flowstate_svc.schemas import inbox_schemas
from fs_flowstate_svc.services import inbox_service


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


def create_inbox_item_via_service(db, user, overrides=None):
    """Helper function to create an inbox item via service to ensure consistency."""
    defaults = {
        "content": "Test content",
        "category": inbox_schemas.InboxCategory.TODO,
        "priority": inbox_schemas.InboxPriority.P3,
        "status": inbox_schemas.InboxStatus.PENDING
    }
    
    if overrides:
        defaults.update(overrides)
    
    item_data = inbox_schemas.InboxItemCreate(**defaults)
    return inbox_service.create_inbox_item(db, user.id, item_data)


class TestCreateInboxItem:
    """Test suite for create_inbox_item function."""
    
    def test_create_inbox_item_success_with_defaults(self, db_session):
        """Test creating inbox item with default schema values."""
        user = create_user(db_session)
        
        item_data = inbox_schemas.InboxItemCreate(content="Test inbox item")
        
        created_item = inbox_service.create_inbox_item(db_session, user.id, item_data)
        
        assert created_item.id is not None
        assert created_item.user_id == user.id
        assert created_item.content == "Test inbox item"
        assert created_item.category == inbox_schemas.InboxCategory.TODO.value
        assert created_item.priority == inbox_schemas.InboxPriority.P3.value
        assert created_item.status == inbox_schemas.InboxStatus.PENDING.value
        assert created_item.created_at is not None
        assert created_item.updated_at is not None
    
    def test_create_inbox_item_success_with_all_fields(self, db_session):
        """Test creating inbox item with all fields specified."""
        user = create_user(db_session)
        
        item_data = inbox_schemas.InboxItemCreate(
            content="Important note",
            category=inbox_schemas.InboxCategory.IDEA,
            priority=inbox_schemas.InboxPriority.P1,
            status=inbox_schemas.InboxStatus.SCHEDULED
        )
        
        created_item = inbox_service.create_inbox_item(db_session, user.id, item_data)
        
        assert created_item.content == "Important note"
        assert created_item.category == inbox_schemas.InboxCategory.IDEA.value
        assert created_item.priority == inbox_schemas.InboxPriority.P1.value
        assert created_item.status == inbox_schemas.InboxStatus.SCHEDULED.value
    
    def test_create_inbox_item_empty_content_raises(self, db_session):
        """Test that empty content raises HTTPException 400."""
        user = create_user(db_session)
        
        item_data = inbox_schemas.InboxItemCreate(content="")
        
        with pytest.raises(HTTPException) as exc_info:
            inbox_service.create_inbox_item(db_session, user.id, item_data)
        
        assert exc_info.value.status_code == 400
        assert "Content cannot be empty" in exc_info.value.detail
    
    def test_create_inbox_item_whitespace_content_raises(self, db_session):
        """Test that whitespace-only content raises HTTPException 400."""
        user = create_user(db_session)
        
        item_data = inbox_schemas.InboxItemCreate(content="   ")
        
        with pytest.raises(HTTPException) as exc_info:
            inbox_service.create_inbox_item(db_session, user.id, item_data)
        
        assert exc_info.value.status_code == 400
        assert "Content cannot be empty" in exc_info.value.detail


class TestGetInboxItem:
    """Test suite for get_inbox_item function."""
    
    def test_get_inbox_item_found(self, db_session):
        """Test retrieving existing inbox item."""
        user = create_user(db_session)
        created_item = create_inbox_item_via_service(db_session, user)
        
        retrieved_item = inbox_service.get_inbox_item(db_session, user.id, created_item.id)
        
        assert retrieved_item is not None
        assert retrieved_item.id == created_item.id
        assert retrieved_item.user_id == user.id
        assert retrieved_item.content == created_item.content
    
    def test_get_inbox_item_not_found_returns_none(self, db_session):
        """Test that non-existent item returns None."""
        user = create_user(db_session)
        random_item_id = uuid.uuid4()
        
        result = inbox_service.get_inbox_item(db_session, user.id, random_item_id)
        
        assert result is None
    
    def test_get_inbox_item_other_user_returns_none(self, db_session):
        """Test that accessing another user's item returns None."""
        user1 = create_user(db_session, "user1", "user1@example.com")
        user2 = create_user(db_session, "user2", "user2@example.com")
        
        item = create_inbox_item_via_service(db_session, user1)
        
        result = inbox_service.get_inbox_item(db_session, user2.id, item.id)
        
        assert result is None


class TestUpdateInboxItem:
    """Test suite for update_inbox_item function."""
    
    def test_update_inbox_item_success_partial(self, db_session):
        """Test updating only one field while others remain unchanged."""
        user = create_user(db_session)
        original_item = create_inbox_item_via_service(db_session, user, {
            "content": "Original content",
            "category": inbox_schemas.InboxCategory.TODO,
            "priority": inbox_schemas.InboxPriority.P3
        })
        
        original_content = original_item.content
        original_category = original_item.category
        original_created_at = original_item.created_at
        original_updated_at = original_item.updated_at  # Capture the timestamp value, not object reference
        
        update_data = inbox_schemas.InboxItemUpdate(priority=inbox_schemas.InboxPriority.P1)
        
        updated_item = inbox_service.update_inbox_item(db_session, user.id, original_item.id, update_data)
        
        assert updated_item.id == original_item.id
        assert updated_item.content == original_content  # Unchanged
        assert updated_item.category == original_category  # Unchanged
        assert updated_item.priority == inbox_schemas.InboxPriority.P1.value  # Updated
        assert updated_item.created_at == original_created_at  # Unchanged
        assert updated_item.updated_at != original_updated_at  # Should be updated
    
    def test_update_inbox_item_all_fields(self, db_session):
        """Test updating all fields."""
        user = create_user(db_session)
        original_item = create_inbox_item_via_service(db_session, user)
        
        update_data = inbox_schemas.InboxItemUpdate(
            content="Updated content",
            category=inbox_schemas.InboxCategory.IDEA,
            priority=inbox_schemas.InboxPriority.P1,
            status=inbox_schemas.InboxStatus.DONE
        )
        
        updated_item = inbox_service.update_inbox_item(db_session, user.id, original_item.id, update_data)
        
        assert updated_item.content == "Updated content"
        assert updated_item.category == inbox_schemas.InboxCategory.IDEA.value
        assert updated_item.priority == inbox_schemas.InboxPriority.P1.value
        assert updated_item.status == inbox_schemas.InboxStatus.DONE.value
    
    def test_update_inbox_item_empty_content_raises(self, db_session):
        """Test that updating to empty content raises HTTPException 400."""
        user = create_user(db_session)
        item = create_inbox_item_via_service(db_session, user)
        
        update_data = inbox_schemas.InboxItemUpdate(content="")
        
        with pytest.raises(HTTPException) as exc_info:
            inbox_service.update_inbox_item(db_session, user.id, item.id, update_data)
        
        assert exc_info.value.status_code == 400
        assert "Content cannot be empty" in exc_info.value.detail
    
    def test_update_inbox_item_not_owned_raises_404(self, db_session):
        """Test that updating another user's item raises HTTPException 404."""
        user1 = create_user(db_session, "user1", "user1@example.com")
        user2 = create_user(db_session, "user2", "user2@example.com")
        
        item = create_inbox_item_via_service(db_session, user1)
        update_data = inbox_schemas.InboxItemUpdate(content="Hacked content")
        
        with pytest.raises(HTTPException) as exc_info:
            inbox_service.update_inbox_item(db_session, user2.id, item.id, update_data)
        
        assert exc_info.value.status_code == 404
        assert "Inbox item not found or not owned" in exc_info.value.detail
    
    def test_update_inbox_item_nonexistent_raises_404(self, db_session):
        """Test that updating non-existent item raises HTTPException 404."""
        user = create_user(db_session)
        random_item_id = uuid.uuid4()
        
        update_data = inbox_schemas.InboxItemUpdate(content="New content")
        
        with pytest.raises(HTTPException) as exc_info:
            inbox_service.update_inbox_item(db_session, user.id, random_item_id, update_data)
        
        assert exc_info.value.status_code == 404
        assert "Inbox item not found or not owned" in exc_info.value.detail


class TestDeleteInboxItem:
    """Test suite for delete_inbox_item function."""
    
    def test_delete_inbox_item_success_returns_true_and_removes(self, db_session):
        """Test successful deletion returns True and removes item."""
        user = create_user(db_session)
        item = create_inbox_item_via_service(db_session, user)
        item_id = item.id
        
        result = inbox_service.delete_inbox_item(db_session, user.id, item_id)
        
        assert result is True
        # Verify item is actually deleted
        deleted_item = inbox_service.get_inbox_item(db_session, user.id, item_id)
        assert deleted_item is None
    
    def test_delete_inbox_item_not_owned_returns_false(self, db_session):
        """Test that deleting another user's item returns False."""
        user1 = create_user(db_session, "user1", "user1@example.com")
        user2 = create_user(db_session, "user2", "user2@example.com")
        
        item = create_inbox_item_via_service(db_session, user1)
        
        result = inbox_service.delete_inbox_item(db_session, user2.id, item.id)
        
        assert result is False
        # Verify item still exists for original user
        still_exists = inbox_service.get_inbox_item(db_session, user1.id, item.id)
        assert still_exists is not None
    
    def test_delete_inbox_item_nonexistent_returns_false(self, db_session):
        """Test that deleting non-existent item returns False."""
        user = create_user(db_session)
        random_item_id = uuid.uuid4()
        
        result = inbox_service.delete_inbox_item(db_session, user.id, random_item_id)
        
        assert result is False


class TestGetInboxItemsFiltering:
    """Test suite for get_inbox_items filtering functionality."""
    
    def setup_test_data(self, db_session):
        """Setup test data with multiple items across categories, priorities, statuses."""
        user1 = create_user(db_session, "user1", "user1@example.com")
        user2 = create_user(db_session, "user2", "user2@example.com")
        
        # User1 items
        items_user1 = [
            create_inbox_item_via_service(db_session, user1, {
                "content": "TODO item P1",
                "category": inbox_schemas.InboxCategory.TODO,
                "priority": inbox_schemas.InboxPriority.P1,
                "status": inbox_schemas.InboxStatus.PENDING
            }),
            create_inbox_item_via_service(db_session, user1, {
                "content": "IDEA item P3",
                "category": inbox_schemas.InboxCategory.IDEA,
                "priority": inbox_schemas.InboxPriority.P3,
                "status": inbox_schemas.InboxStatus.SCHEDULED
            }),
            create_inbox_item_via_service(db_session, user1, {
                "content": "NOTE item P5",
                "category": inbox_schemas.InboxCategory.NOTE,
                "priority": inbox_schemas.InboxPriority.P5,
                "status": inbox_schemas.InboxStatus.DONE
            }),
            create_inbox_item_via_service(db_session, user1, {
                "content": "Another TODO P2",
                "category": inbox_schemas.InboxCategory.TODO,
                "priority": inbox_schemas.InboxPriority.P2,
                "status": inbox_schemas.InboxStatus.ARCHIVED
            })
        ]
        
        # User2 items (should not appear in user1 results)
        items_user2 = [
            create_inbox_item_via_service(db_session, user2, {
                "content": "User2 TODO",
                "category": inbox_schemas.InboxCategory.TODO,
                "priority": inbox_schemas.InboxPriority.P1,
                "status": inbox_schemas.InboxStatus.PENDING
            })
        ]
        
        return user1, user2, items_user1, items_user2
    
    def test_filter_by_category(self, db_session):
        """Test filtering by category."""
        user1, user2, items_user1, items_user2 = self.setup_test_data(db_session)
        
        filters = inbox_schemas.InboxItemFilter(category=inbox_schemas.InboxCategory.TODO)
        todo_items = inbox_service.get_inbox_items(db_session, user1.id, filters)
        
        assert len(todo_items) == 2
        for item in todo_items:
            assert item.category == inbox_schemas.InboxCategory.TODO.value
            assert item.user_id == user1.id
    
    def test_filter_by_status(self, db_session):
        """Test filtering by status."""
        user1, user2, items_user1, items_user2 = self.setup_test_data(db_session)
        
        filters = inbox_schemas.InboxItemFilter(status=inbox_schemas.InboxStatus.PENDING)
        pending_items = inbox_service.get_inbox_items(db_session, user1.id, filters)
        
        assert len(pending_items) == 1
        assert pending_items[0].status == inbox_schemas.InboxStatus.PENDING.value
        assert pending_items[0].user_id == user1.id
    
    def test_filter_by_priority_range_min_only(self, db_session):
        """Test filtering by minimum priority."""
        user1, user2, items_user1, items_user2 = self.setup_test_data(db_session)
        
        filters = inbox_schemas.InboxItemFilter(priority_min=inbox_schemas.InboxPriority.P3)
        items = inbox_service.get_inbox_items(db_session, user1.id, filters)
        
        assert len(items) == 2  # P3 and P5 items
        for item in items:
            assert item.priority >= inbox_schemas.InboxPriority.P3.value
            assert item.user_id == user1.id
    
    def test_filter_by_priority_range_max_only(self, db_session):
        """Test filtering by maximum priority."""
        user1, user2, items_user1, items_user2 = self.setup_test_data(db_session)
        
        filters = inbox_schemas.InboxItemFilter(priority_max=inbox_schemas.InboxPriority.P2)
        items = inbox_service.get_inbox_items(db_session, user1.id, filters)
        
        assert len(items) == 2  # P1 and P2 items
        for item in items:
            assert item.priority <= inbox_schemas.InboxPriority.P2.value
            assert item.user_id == user1.id
    
    def test_filter_by_priority_range_min_max(self, db_session):
        """Test filtering by both minimum and maximum priority."""
        user1, user2, items_user1, items_user2 = self.setup_test_data(db_session)
        
        filters = inbox_schemas.InboxItemFilter(
            priority_min=inbox_schemas.InboxPriority.P2,
            priority_max=inbox_schemas.InboxPriority.P3
        )
        items = inbox_service.get_inbox_items(db_session, user1.id, filters)
        
        assert len(items) == 2  # P2 and P3 items
        for item in items:
            assert inbox_schemas.InboxPriority.P2.value <= item.priority <= inbox_schemas.InboxPriority.P3.value
            assert item.user_id == user1.id
    
    def test_filter_combined_and_pagination_skip_limit(self, db_session):
        """Test combined filters with pagination."""
        user1, user2, items_user1, items_user2 = self.setup_test_data(db_session)
        
        # Filter for TODO items only
        filters = inbox_schemas.InboxItemFilter(category=inbox_schemas.InboxCategory.TODO)
        
        # Get first item (skip=0, limit=1)
        first_page = inbox_service.get_inbox_items(db_session, user1.id, filters, skip=0, limit=1)
        assert len(first_page) == 1
        
        # Get second item (skip=1, limit=1)
        second_page = inbox_service.get_inbox_items(db_session, user1.id, filters, skip=1, limit=1)
        assert len(second_page) == 1
        
        # Items should be different
        assert first_page[0].id != second_page[0].id
        
        # Both should be TODO items for user1
        for item in first_page + second_page:
            assert item.category == inbox_schemas.InboxCategory.TODO.value
            assert item.user_id == user1.id
    
    def test_get_all_items_no_filters(self, db_session):
        """Test getting all items without filters ensures only target user items returned."""
        user1, user2, items_user1, items_user2 = self.setup_test_data(db_session)
        
        empty_filters = inbox_schemas.InboxItemFilter()
        all_user1_items = inbox_service.get_inbox_items(db_session, user1.id, empty_filters)
        
        assert len(all_user1_items) == 4  # All user1 items
        for item in all_user1_items:
            assert item.user_id == user1.id
        
        # Verify user2 gets only their items
        all_user2_items = inbox_service.get_inbox_items(db_session, user2.id, empty_filters)
        assert len(all_user2_items) == 1
        assert all_user2_items[0].user_id == user2.id


class TestBulkOperations:
    """Test suite for bulk operations."""
    
    def setup_bulk_test_data(self, db_session):
        """Setup test data for bulk operations."""
        user1 = create_user(db_session, "user1", "user1@example.com")
        user2 = create_user(db_session, "user2", "user2@example.com")
        
        # Create items for user1
        items_user1 = [
            create_inbox_item_via_service(db_session, user1, {"status": inbox_schemas.InboxStatus.PENDING}),
            create_inbox_item_via_service(db_session, user1, {"status": inbox_schemas.InboxStatus.PENDING}),
            create_inbox_item_via_service(db_session, user1, {"status": inbox_schemas.InboxStatus.SCHEDULED})
        ]
        
        # Create item for user2
        items_user2 = [
            create_inbox_item_via_service(db_session, user2, {"status": inbox_schemas.InboxStatus.PENDING})
        ]
        
        return user1, user2, items_user1, items_user2
    
    def test_bulk_update_status_updates_count_and_only_target_user(self, db_session):
        """Test bulk status update affects only target user's items and returns correct count."""
        user1, user2, items_user1, items_user2 = self.setup_bulk_test_data(db_session)
        
        # Update first two user1 items to DONE
        target_ids = [items_user1[0].id, items_user1[1].id]
        updated_count = inbox_service.bulk_update_inbox_item_status(
            db_session, user1.id, target_ids, inbox_schemas.InboxStatus.DONE
        )
        
        assert updated_count == 2
        
        # Verify updates
        updated_item1 = inbox_service.get_inbox_item(db_session, user1.id, items_user1[0].id)
        updated_item2 = inbox_service.get_inbox_item(db_session, user1.id, items_user1[1].id)
        unchanged_item3 = inbox_service.get_inbox_item(db_session, user1.id, items_user1[2].id)
        
        assert updated_item1.status == inbox_schemas.InboxStatus.DONE.value
        assert updated_item2.status == inbox_schemas.InboxStatus.DONE.value
        assert unchanged_item3.status == inbox_schemas.InboxStatus.SCHEDULED.value  # Unchanged
        
        # Verify user2's items are unaffected
        user2_item = inbox_service.get_inbox_item(db_session, user2.id, items_user2[0].id)
        assert user2_item.status == inbox_schemas.InboxStatus.PENDING.value
    
    def test_bulk_update_status_with_empty_ids_returns_zero(self, db_session):
        """Test bulk update with empty list returns 0."""
        user1, user2, items_user1, items_user2 = self.setup_bulk_test_data(db_session)
        
        updated_count = inbox_service.bulk_update_inbox_item_status(
            db_session, user1.id, [], inbox_schemas.InboxStatus.DONE
        )
        
        assert updated_count == 0
    
    def test_bulk_update_status_with_other_user_items_returns_zero(self, db_session):
        """Test bulk update with another user's item IDs returns 0."""
        user1, user2, items_user1, items_user2 = self.setup_bulk_test_data(db_session)
        
        # Try to update user2's items using user1's account
        user2_ids = [item.id for item in items_user2]
        updated_count = inbox_service.bulk_update_inbox_item_status(
            db_session, user1.id, user2_ids, inbox_schemas.InboxStatus.DONE
        )
        
        assert updated_count == 0
        
        # Verify user2's items are unchanged
        user2_item = inbox_service.get_inbox_item(db_session, user2.id, items_user2[0].id)
        assert user2_item.status == inbox_schemas.InboxStatus.PENDING.value
    
    def test_bulk_archive_items_sets_archived(self, db_session):
        """Test bulk archive sets status to ARCHIVED."""
        user1, user2, items_user1, items_user2 = self.setup_bulk_test_data(db_session)
        
        # Archive first two user1 items
        target_ids = [items_user1[0].id, items_user1[1].id]
        archived_count = inbox_service.bulk_archive_inbox_items(db_session, user1.id, target_ids)
        
        assert archived_count == 2
        
        # Verify items are archived
        archived_item1 = inbox_service.get_inbox_item(db_session, user1.id, items_user1[0].id)
        archived_item2 = inbox_service.get_inbox_item(db_session, user1.id, items_user1[1].id)
        
        assert archived_item1.status == inbox_schemas.InboxStatus.ARCHIVED.value
        assert archived_item2.status == inbox_schemas.InboxStatus.ARCHIVED.value
    
    def test_bulk_archive_empty_list_returns_zero(self, db_session):
        """Test bulk archive with empty list returns 0."""
        user1, user2, items_user1, items_user2 = self.setup_bulk_test_data(db_session)
        
        archived_count = inbox_service.bulk_archive_inbox_items(db_session, user1.id, [])
        
        assert archived_count == 0


class TestSchemaValidationEdgeCases:
    """Test edge cases with schema validation and enum mapping."""
    
    def test_service_stores_enum_values_in_db(self, db_session):
        """Test that service correctly stores enum .value in database."""
        user = create_user(db_session)
        
        item_data = inbox_schemas.InboxItemCreate(
            content="Test enum storage",
            category=inbox_schemas.InboxCategory.IDEA,
            priority=inbox_schemas.InboxPriority.P1,
            status=inbox_schemas.InboxStatus.SCHEDULED
        )
        
        created_item = inbox_service.create_inbox_item(db_session, user.id, item_data)
        
        # Verify raw database values match enum values
        assert created_item.category == "IDEA"
        assert created_item.priority == 1
        assert created_item.status == "SCHEDULED"
    
    def test_filtering_uses_enum_values(self, db_session):
        """Test that filtering correctly uses enum .value for comparison."""
        user = create_user(db_session)
        
        # Create item with specific enum values
        create_inbox_item_via_service(db_session, user, {
            "category": inbox_schemas.InboxCategory.IDEA,
            "priority": inbox_schemas.InboxPriority.P2,
            "status": inbox_schemas.InboxStatus.DONE
        })
        
        # Test each filter type
        category_filter = inbox_schemas.InboxItemFilter(category=inbox_schemas.InboxCategory.IDEA)
        category_results = inbox_service.get_inbox_items(db_session, user.id, category_filter)
        assert len(category_results) == 1
        
        priority_filter = inbox_schemas.InboxItemFilter(priority_min=inbox_schemas.InboxPriority.P2)
        priority_results = inbox_service.get_inbox_items(db_session, user.id, priority_filter)
        assert len(priority_results) == 1
        
        status_filter = inbox_schemas.InboxItemFilter(status=inbox_schemas.InboxStatus.DONE)
        status_results = inbox_service.get_inbox_items(db_session, user.id, status_filter)
        assert len(status_results) == 1
