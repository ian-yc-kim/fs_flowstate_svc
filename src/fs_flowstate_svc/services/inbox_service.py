"""Inbox service logic for CRUD operations, filtering, and bulk operations."""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import Session

from fs_flowstate_svc.models.flowstate_models import InboxItems, Events
from fs_flowstate_svc.schemas import inbox_schemas, event_schemas
from fs_flowstate_svc.services import event_service
from fs_flowstate_svc.schemas.inbox_schemas import InboxItemResponse
from fs_flowstate_svc.schemas.websocket_schemas import WebSocketMessage
from fs_flowstate_svc.api.websocket_router import connection_manager

logger = logging.getLogger(__name__)


def create_inbox_item(db: Session, user_id: uuid.UUID, item_data: inbox_schemas.InboxItemCreate) -> InboxItems:
    """Create a new inbox item with validation.
    
    Args:
        db: Database session
        user_id: User ID creating the item
        item_data: Inbox item creation data
        
    Returns:
        Created inbox item object
        
    Raises:
        HTTPException: If validation fails
    """
    try:
        # Validate content is not empty
        if not item_data.content or not item_data.content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content cannot be empty"
            )
        
        # Create inbox item object
        db_item = InboxItems(
            user_id=user_id,
            content=item_data.content.strip(),
            category=item_data.category.value,
            priority=item_data.priority.value,
            status=item_data.status.value
        )
        
        # Save to database
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        
        # Broadcast creation
        try:
            payload = InboxItemResponse.model_validate(db_item).model_dump(mode="json")
            msg = WebSocketMessage(type="inbox_item_created", payload=payload)
            connection_manager.broadcast_to_user(str(user_id), msg)
        except Exception as e:
            logger.error(e, exc_info=True)

        return db_item
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating inbox item: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed"
        )


def get_inbox_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> Optional[InboxItems]:
    """Retrieve an inbox item by ID with ownership verification.
    
    Args:
        db: Database session
        item_id: Item ID to retrieve
        user_id: User ID for ownership verification
        
    Returns:
        Inbox item object or None if not found/not owned
    """
    try:
        stmt = select(InboxItems).where(
            InboxItems.id == item_id,
            InboxItems.user_id == user_id
        )
        result = db.execute(stmt)
        return result.scalar_one_or_none()
        
    except Exception as e:
        logger.error(f"Error retrieving inbox item: {e}", exc_info=True)
        return None


def get_inbox_items(
    db: Session, 
    user_id: uuid.UUID, 
    filters: inbox_schemas.InboxItemFilter, 
    skip: int = 0, 
    limit: int = 100
) -> List[InboxItems]:
    """Retrieve inbox items for a user with optional filters.
    
    Args:
        db: Database session
        user_id: User ID to get items for
        filters: Filter criteria
        skip: Number of items to skip
        limit: Maximum number of items to return
        
    Returns:
        List of inbox item objects
    """
    try:
        # Base query
        query = select(InboxItems).where(InboxItems.user_id == user_id)
        
        clauses = []

        # Categories multi-select
        if getattr(filters, "categories", None):
            vals = [c.value for c in filters.categories]
            if vals:
                clauses.append(InboxItems.category.in_(vals))

        # Statuses multi-select
        if getattr(filters, "statuses", None):
            vals = [s.value for s in filters.statuses]
            if vals:
                clauses.append(InboxItems.status.in_(vals))

        # Priorities multi-select takes precedence over min/max
        if getattr(filters, "priorities", None):
            vals = [p.value for p in filters.priorities]
            if vals:
                clauses.append(InboxItems.priority.in_(vals))
        else:
            # Apply min/max only when priorities list not provided
            if filters.priority_min is not None:
                clauses.append(InboxItems.priority >= filters.priority_min.value)
            if filters.priority_max is not None:
                clauses.append(InboxItems.priority <= filters.priority_max.value)

        # Combine clauses using AND/OR based on filter_logic
        if clauses:
            logic = (filters.filter_logic or "AND").upper()
            if logic == "OR":
                combined = or_(*clauses)
            else:
                combined = and_(*clauses)
            query = query.where(combined)

        # Order by created_at descending (newest first)
        query = query.order_by(InboxItems.created_at.desc())

        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        result = db.execute(query)
        return result.scalars().all()
        
    except Exception as e:
        logger.error(f"Error retrieving inbox items: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed"
        )


def update_inbox_item(
    db: Session, 
    user_id: uuid.UUID, 
    item_id: uuid.UUID, 
    item_update: inbox_schemas.InboxItemUpdate
) -> InboxItems:
    """Update an existing inbox item with validation.
    
    Args:
        db: Database session
        user_id: User ID for ownership verification
        item_id: Item ID to update
        item_update: Item update data
        
    Returns:
        Updated inbox item object
        
    Raises:
        HTTPException: If validation fails, item not found, or access denied
    """
    try:
        # Get existing item with ownership check
        existing_item = get_inbox_item(db, user_id, item_id)
        
        if existing_item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inbox item not found or not owned"
            )
        
        # Apply updates only for provided fields
        if item_update.content is not None:
            if not item_update.content.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Content cannot be empty"
                )
            existing_item.content = item_update.content.strip()
        
        if item_update.category is not None:
            existing_item.category = item_update.category.value
        
        if item_update.priority is not None:
            existing_item.priority = item_update.priority.value
        
        if item_update.status is not None:
            existing_item.status = item_update.status.value
        
        # Explicitly update the updated_at timestamp to ensure it changes
        existing_item.updated_at = datetime.utcnow()
        
        # Save changes
        db.commit()
        db.refresh(existing_item)

        # Broadcast update
        try:
            payload = InboxItemResponse.model_validate(existing_item).model_dump(mode="json")
            msg = WebSocketMessage(type="inbox_item_updated", payload=payload)
            connection_manager.broadcast_to_user(str(user_id), msg)
        except Exception as e:
            logger.error(e, exc_info=True)

        return existing_item
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating inbox item: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed"
        )


def delete_inbox_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> bool:
    """Delete an inbox item.
    
    Args:
        db: Database session
        user_id: User ID for ownership verification
        item_id: Item ID to delete
        
    Returns:
        True if deleted, False if not found or not owned
    """
    try:
        # Get existing item with ownership check
        existing_item = get_inbox_item(db, user_id, item_id)
        
        if existing_item is None:
            return False
        
        # Delete the item
        db.delete(existing_item)
        db.commit()

        # Broadcast deletion
        try:
            payload = {"inbox_item_id": str(item_id)}
            msg = WebSocketMessage(type="inbox_item_deleted", payload=payload)
            connection_manager.broadcast_to_user(str(user_id), msg)
        except Exception as e:
            logger.error(e, exc_info=True)

        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting inbox item: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed"
        )


def bulk_update_inbox_item_status(
    db: Session, 
    user_id: uuid.UUID, 
    item_ids: List[uuid.UUID], 
    new_status: inbox_schemas.InboxStatus
) -> int:
    """Bulk update inbox item status.
    
    Args:
        db: Database session
        user_id: User ID for ownership verification
        item_ids: List of item IDs to update
        new_status: New status to set
        
    Returns:
        Number of items updated
    """
    try:
        # Handle empty list
        if not item_ids:
            return 0
        
        # Construct update statement
        stmt = update(InboxItems).where(
            InboxItems.user_id == user_id,
            InboxItems.id.in_(item_ids)
        ).values(status=new_status.value, updated_at=func.now())
        
        # Execute update
        result = db.execute(stmt)
        db.commit()
        
        # Efficiently fetch updated items in a single query to avoid per-item DB calls
        try:
            sel = select(InboxItems).where(
                InboxItems.user_id == user_id,
                InboxItems.id.in_(item_ids)
            )
            result_items = db.execute(sel)
            items = result_items.scalars().all()
            for item in items:
                try:
                    payload = InboxItemResponse.model_validate(item).model_dump(mode="json")
                    msg = WebSocketMessage(type="inbox_item_updated", payload=payload)
                    connection_manager.broadcast_to_user(str(user_id), msg)
                except Exception as e:
                    logger.error(e, exc_info=True)
        except Exception as e:
            logger.error("Failed fetching items after bulk update", exc_info=True)

        return result.rowcount
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error bulk updating inbox item status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed"
        )


def bulk_archive_inbox_items(db: Session, user_id: uuid.UUID, item_ids: List[uuid.UUID]) -> int:
    """Bulk archive inbox items.
    
    Args:
        db: Database session
        user_id: User ID for ownership verification
        item_ids: List of item IDs to archive
        
    Returns:
        Number of items archived
    """
    return bulk_update_inbox_item_status(db, user_id, item_ids, inbox_schemas.InboxStatus.ARCHIVED)


def convert_inbox_item_to_event(db: Session, user_id: uuid.UUID, conversion_data: inbox_schemas.InboxItemConvertToEvent) -> Events:
    """Convert an existing inbox item into a calendar event.
    
    Args:
        db: Database session
        user_id: User ID for ownership verification
        conversion_data: Conversion request data
        
    Returns:
        Created event object
        
    Raises:
        HTTPException: If validation fails, item not found, or event creation fails
    """
    try:
        # Retrieve the inbox item with ownership check
        inbox_item = get_inbox_item(db, user_id, conversion_data.item_id)
        
        if inbox_item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inbox item not found or not owned"
            )
        
        # Prepare event title with truncation for safety
        if conversion_data.event_title is not None:
            event_title = conversion_data.event_title.strip()[:255]
        else:
            event_title = inbox_item.content.strip()[:255]
        
        # Prepare event description with length check
        if conversion_data.event_description is not None:
            event_description = conversion_data.event_description
        else:
            content_stripped = inbox_item.content.strip()
            if len(content_stripped) <= 255:
                event_description = content_stripped
            else:
                event_description = ""
        
        # Prepare event category
        event_category = conversion_data.event_category or inbox_item.category
        
        # Prepare event metadata
        event_metadata = dict(conversion_data.event_metadata or {})
        event_metadata["converted_from_inbox_item_id"] = str(inbox_item.id)
        
        # Construct EventCreate object
        event_create = event_schemas.EventCreate(
            title=event_title,
            description=event_description,
            start_time=conversion_data.start_time,
            end_time=conversion_data.end_time,
            is_all_day=conversion_data.is_all_day,
            is_recurring=conversion_data.is_recurring,
            category=event_category,
            metadata=event_metadata
        )
        
        # Create the event using event service (this will commit its own transaction)
        created_event = event_service.create_event(db, user_id, event_create)
        
        # Capture the event ID before the object becomes detached
        created_event_id = created_event.id
        
        # Update the original inbox item status to SCHEDULED in a separate statement
        # Using update statement with explicit commit to avoid session issues
        update_stmt = update(InboxItems).where(
            InboxItems.id == inbox_item.id,
            InboxItems.user_id == user_id
        ).values(
            status=inbox_schemas.InboxStatus.SCHEDULED.value,
            updated_at=func.now()
        )
        
        db.execute(update_stmt)
        db.commit()

        # Broadcast inbox item updated
        try:
            refreshed_item = get_inbox_item(db, user_id, inbox_item.id)
            if refreshed_item is not None:
                payload = InboxItemResponse.model_validate(refreshed_item).model_dump(mode="json")
                msg = WebSocketMessage(type="inbox_item_updated", payload=payload)
                connection_manager.broadcast_to_user(str(user_id), msg)
        except Exception as e:
            logger.error(e, exc_info=True)

        # Re-query the created event to return a fresh instance
        event_stmt = select(Events).where(
            Events.id == created_event_id,
            Events.user_id == user_id
        )
        result = db.execute(event_stmt)
        final_event = result.scalar_one()
        
        return final_event
        
    except HTTPException:
        # Propagate HTTP exceptions from event service or validation
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error converting inbox item to event: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed"
        )
