"""Event service logic for CRUD operations, validation, and conflict detection."""

import logging
from datetime import datetime, timezone, time
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, and_, not_
from sqlalchemy.orm import Session

from fs_flowstate_svc.models.flowstate_models import Events, ReminderSettings
from fs_flowstate_svc.schemas.event_schemas import EventCreate, EventUpdate, EventFilter

logger = logging.getLogger(__name__)


def _ensure_tz(dt: datetime) -> datetime:
    """Ensure datetime has timezone info, defaulting to UTC if naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _normalize_all_day_times(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Normalize all-day event times to 00:00:00 and 23:59:59 preserving timezone info."""
    # Get timezone info from inputs or default to UTC
    start_tz = start.tzinfo if start.tzinfo else timezone.utc
    end_tz = end.tzinfo if end.tzinfo else timezone.utc
    
    # Normalize to start of day and end of day
    normalized_start = start.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=start_tz)
    normalized_end = end.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=end_tz)
    
    return normalized_start, normalized_end


def _to_storage_datetime(dt: datetime) -> datetime:
    """Convert datetime for storage, handling timezone appropriately for the database."""
    # Ensure timezone-aware datetime for internal processing
    dt_with_tz = _ensure_tz(dt)
    
    # Convert to UTC and return as naive datetime for consistent storage
    # This ensures SQLite compatibility while maintaining UTC consistency
    return dt_with_tz.astimezone(timezone.utc).replace(tzinfo=None)


def _check_conflicts(db: Session, user_id: UUID, start: datetime, end: datetime, exclude_event_id: Optional[UUID] = None) -> bool:
    """Check if there are conflicting events for the user in the given time range."""
    try:
        # Convert to storage format for consistent comparison
        start_storage = _to_storage_datetime(start)
        end_storage = _to_storage_datetime(end)
        
        query = select(Events).where(
            Events.user_id == user_id,
            Events.start_time < end_storage,
            Events.end_time > start_storage
        )
        
        if exclude_event_id:
            query = query.where(Events.id != exclude_event_id)
        
        result = db.execute(query)
        conflicting_events = result.scalars().all()
        
        return len(conflicting_events) > 0
    except Exception as e:
        logger.error(f"Error checking event conflicts: {e}", exc_info=True)
        raise


def _publish_event_created(event: Events) -> None:
    """Placeholder function for publishing event created events."""
    logger.info(f"Event created: {event.id} - {event.title}")


def _publish_event_updated(event: Events) -> None:
    """Placeholder function for publishing event updated events."""
    logger.info(f"Event updated: {event.id} - {event.title}")


def _publish_event_deleted(event_id: UUID) -> None:
    """Placeholder function for publishing event deleted events."""
    logger.info(f"Event deleted: {event_id}")


def create_event(db: Session, user_id: UUID, event_data: EventCreate) -> Events:
    """Create a new event with validation and conflict detection.
    
    Args:
        db: Database session
        user_id: User ID creating the event
        event_data: Event creation data
        
    Returns:
        Created event object
        
    Raises:
        HTTPException: If validation fails or conflicts exist
    """
    try:
        # Validate title
        if not event_data.title or not event_data.title.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Event title cannot be empty"
            )
        
        # Handle timezone and all-day normalization
        start_time = _ensure_tz(event_data.start_time)
        end_time = _ensure_tz(event_data.end_time)
        
        if event_data.is_all_day:
            start_time, end_time = _normalize_all_day_times(start_time, end_time)
        
        # Validate time order (compare timezone-aware datetimes)
        if start_time >= end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Event start time must be before end time"
            )
        
        # Check for conflicts (using timezone-aware datetimes)
        if _check_conflicts(db, user_id, start_time, end_time):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Event time conflicts with existing events"
            )
        
        # Convert to storage format
        start_storage = _to_storage_datetime(start_time)
        end_storage = _to_storage_datetime(end_time)
        
        # Create event object
        db_event = Events(
            user_id=user_id,
            title=event_data.title.strip(),
            description=event_data.description,
            start_time=start_storage,
            end_time=end_storage,
            category=event_data.category,
            is_all_day=event_data.is_all_day,
            is_recurring=event_data.is_recurring,
            event_metadata=event_data.metadata
        )
        
        # Save to database
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        
        # Publish event created
        _publish_event_created(db_event)
        
        return db_event
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating event: {e}", exc_info=True)
        raise


def get_event(db: Session, event_id: UUID, user_id: UUID) -> Events:
    """Retrieve an event by ID with ownership verification.
    
    Args:
        db: Database session
        event_id: Event ID to retrieve
        user_id: User ID for ownership verification
        
    Returns:
        Event object
        
    Raises:
        HTTPException: 404 if not found, 403 if not owned by user
    """
    try:
        stmt = select(Events).where(Events.id == event_id)
        result = db.execute(stmt)
        event = result.scalar_one_or_none()
        
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        
        if event.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: event belongs to another user"
            )
        
        return event
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving event: {e}", exc_info=True)
        raise


def get_events(db: Session, user_id: UUID, filters: EventFilter) -> List[Events]:
    """Retrieve events for a user with optional filters.
    
    Args:
        db: Database session
        user_id: User ID to get events for
        filters: Filter criteria
        
    Returns:
        List of event objects
    """
    try:
        # Base query
        query = select(Events).where(Events.user_id == user_id)
        
        # Apply date filters (convert to storage format for consistent comparison)
        if filters.start_date:
            start_dt = datetime.combine(filters.start_date, time(0, 0, 0), tzinfo=timezone.utc)
            start_storage = _to_storage_datetime(start_dt)
            query = query.where(Events.start_time >= start_storage)
        
        if filters.end_date:
            end_dt = datetime.combine(filters.end_date, time(23, 59, 59), tzinfo=timezone.utc)
            end_storage = _to_storage_datetime(end_dt)
            query = query.where(Events.end_time <= end_storage)
        
        # Apply category filter
        if filters.category:
            query = query.where(Events.category == filters.category)
        
        # Order by start time
        query = query.order_by(Events.start_time.asc())
        
        result = db.execute(query)
        return result.scalars().all()
        
    except Exception as e:
        logger.error(f"Error retrieving events: {e}", exc_info=True)
        raise


def update_event(db: Session, event_id: UUID, user_id: UUID, event_data: EventUpdate) -> Events:
    """Update an existing event with validation and conflict detection.
    
    Args:
        db: Database session
        event_id: Event ID to update
        user_id: User ID for ownership verification
        event_data: Event update data
        
    Returns:
        Updated event object
        
    Raises:
        HTTPException: If validation fails, conflicts exist, or access denied
    """
    try:
        # Retrieve existing event (enforces ownership)
        existing_event = get_event(db, event_id, user_id)
        
        # Track if we need to revalidate times
        time_changed = False
        current_start = existing_event.start_time
        current_end = existing_event.end_time
        
        # Apply updates
        if event_data.title is not None:
            if not event_data.title.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Event title cannot be empty"
                )
            existing_event.title = event_data.title.strip()
        
        if event_data.description is not None:
            existing_event.description = event_data.description
        
        if event_data.start_time is not None:
            current_start = _ensure_tz(event_data.start_time)
            time_changed = True
        
        if event_data.end_time is not None:
            current_end = _ensure_tz(event_data.end_time)
            time_changed = True
        
        if event_data.category is not None:
            existing_event.category = event_data.category
        
        if event_data.is_all_day is not None:
            existing_event.is_all_day = event_data.is_all_day
            time_changed = True
        
        if event_data.is_recurring is not None:
            existing_event.is_recurring = event_data.is_recurring
        
        if event_data.metadata is not None:
            existing_event.event_metadata = event_data.metadata
        
        # Handle all-day normalization if needed
        if existing_event.is_all_day and time_changed:
            current_start, current_end = _normalize_all_day_times(current_start, current_end)
        
        # Validate time order if times changed
        if time_changed:
            if current_start >= current_end:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Event start time must be before end time"
                )
            
            # Check for conflicts (excluding this event)
            if _check_conflicts(db, user_id, current_start, current_end, event_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Event time conflicts with existing events"
                )
            
            # Update the database fields with storage format
            existing_event.start_time = _to_storage_datetime(current_start)
            existing_event.end_time = _to_storage_datetime(current_end)
        
        # Save changes
        db.commit()
        db.refresh(existing_event)
        
        # Publish event updated
        _publish_event_updated(existing_event)
        
        return existing_event
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating event: {e}", exc_info=True)
        raise


def delete_event(db: Session, event_id: UUID, user_id: UUID) -> None:
    """Delete an event and handle reminder cleanup.
    
    Args:
        db: Database session
        event_id: Event ID to delete
        user_id: User ID for ownership verification
        
    Raises:
        HTTPException: If event not found or access denied
    """
    try:
        # Retrieve existing event (enforces ownership)
        existing_event = get_event(db, event_id, user_id)
        
        # Nullify reminder settings that reference this event
        reminder_stmt = select(ReminderSettings).where(
            and_(
                ReminderSettings.user_id == user_id,
                ReminderSettings.event_id == event_id
            )
        )
        reminder_result = db.execute(reminder_stmt)
        reminders = reminder_result.scalars().all()
        
        for reminder in reminders:
            reminder.event_id = None
        
        db.commit()
        
        # Delete the event
        db.delete(existing_event)
        db.commit()
        
        # Publish event deleted
        _publish_event_deleted(event_id)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting event: {e}", exc_info=True)
        raise
