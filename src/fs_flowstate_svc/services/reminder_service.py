"""Reminder service logic for default/user-specific preparation time retrieval and reminder calculation."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from fs_flowstate_svc.config import settings
from fs_flowstate_svc.models.flowstate_models import UserReminderPreference, Events, ReminderSettings

logger = logging.getLogger(__name__)


def _normalize_category(category: str) -> str:
    """Normalize category string by trimming spaces and converting to lowercase.
    
    Args:
        category: Raw category string
        
    Returns:
        Normalized category string
    """
    return category.strip().lower()


def _get_default_preparation_time(category: str) -> int:
    """Get default preparation time for an event category.
    
    Args:
        category: Event category (will be normalized)
        
    Returns:
        Default preparation time in minutes
    """
    normalized_category = _normalize_category(category)
    return settings.DEFAULT_PREPARATION_TIMES.get(
        normalized_category, 
        settings.DEFAULT_PREPARATION_TIMES.get("general", 5)
    )


def _to_storage_datetime(dt: datetime) -> datetime:
    """Convert datetime for storage, handling timezone appropriately for the database.
    
    This function mirrors the logic in event_service.py to ensure consistent datetime handling.
    
    Args:
        dt: Datetime to convert
        
    Returns:
        Naive UTC datetime for consistent storage/comparison
    """
    # Ensure timezone-aware datetime
    if dt.tzinfo is None:
        dt_with_tz = dt.replace(tzinfo=timezone.utc)
    else:
        dt_with_tz = dt
    
    # Convert to UTC and return as naive datetime for consistent storage
    return dt_with_tz.astimezone(timezone.utc).replace(tzinfo=None)


def get_user_preference(db: Session, user_id: UUID, category: str) -> Optional[UserReminderPreference]:
    """Retrieve user-specific reminder preference for an event category.
    
    Args:
        db: Database session
        user_id: User UUID
        category: Event category (will be normalized)
        
    Returns:
        UserReminderPreference object if found, None otherwise
        
    Raises:
        Exception: If database operation fails
    """
    try:
        normalized_category = _normalize_category(category)
        
        stmt = select(UserReminderPreference).where(
            UserReminderPreference.user_id == user_id,
            UserReminderPreference.event_category == normalized_category
        )
        
        result = db.execute(stmt)
        return result.scalar_one_or_none()
        
    except Exception as e:
        logger.error(f"Error retrieving user preference for user {user_id}, category '{category}': {e}", exc_info=True)
        raise


def set_user_preference(
    db: Session, 
    user_id: UUID, 
    category: str, 
    preparation_time_minutes: int, 
    is_custom: bool
) -> UserReminderPreference:
    """Create or update user-specific reminder preference for an event category.
    
    Args:
        db: Database session
        user_id: User UUID
        category: Event category (will be normalized)
        preparation_time_minutes: Preparation time in minutes
        is_custom: Whether this is a custom preference
        
    Returns:
        Created or updated UserReminderPreference object
        
    Raises:
        Exception: If database operation fails
    """
    try:
        normalized_category = _normalize_category(category)
        
        # Look up existing preference
        existing_preference = get_user_preference(db, user_id, normalized_category)
        
        if existing_preference:
            # Update existing preference
            existing_preference.preparation_time_minutes = preparation_time_minutes
            existing_preference.is_custom = is_custom
            preference = existing_preference
        else:
            # Create new preference
            preference = UserReminderPreference(
                user_id=user_id,
                event_category=normalized_category,
                preparation_time_minutes=preparation_time_minutes,
                is_custom=is_custom
            )
            db.add(preference)
        
        db.commit()
        db.refresh(preference)
        
        return preference
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error setting user preference for user {user_id}, category '{category}': {e}", exc_info=True)
        raise


def _calculate_basic_reminder_time(event_start_time: datetime, preparation_time_minutes: int) -> datetime:
    """Calculate basic reminder time by subtracting preparation time from event start time.
    
    Args:
        event_start_time: Event start time
        preparation_time_minutes: Preparation time in minutes
        
    Returns:
        Calculated reminder time
    """
    return event_start_time - timedelta(minutes=preparation_time_minutes)


def _adjust_for_consecutive_events(
    db: Session,
    user_id: UUID,
    current_event: Events,
    initial_reminder_time: datetime,
    effective_preparation_time_minutes: int
) -> datetime:
    """Adjust reminder time to avoid conflicts with immediately preceding events.
    
    Args:
        db: Database session
        user_id: User UUID
        current_event: Current event to calculate reminder for
        initial_reminder_time: Initially calculated reminder time
        effective_preparation_time_minutes: Effective preparation time in minutes
        
    Returns:
        Adjusted reminder time that avoids conflicts with preceding events
        
    Raises:
        Exception: If database operation fails
    """
    try:
        # Query for the immediately preceding event
        stmt = select(Events).where(
            Events.user_id == user_id,
            Events.end_time <= current_event.start_time
        ).order_by(Events.end_time.desc()).limit(1)
        
        result = db.execute(stmt)
        preceding_event = result.scalar_one_or_none()
        
        if preceding_event is None:
            # No preceding event, return initial reminder time
            return initial_reminder_time
        
        # Convert initial reminder time to storage format for consistent comparison
        # (database stores naive UTC datetimes)
        initial_reminder_storage = _to_storage_datetime(initial_reminder_time)
        
        # Check if initial reminder time conflicts with preceding event
        # preceding_event.end_time is already in storage format (naive UTC)
        if initial_reminder_storage <= preceding_event.end_time:
            # Conflict detected: adjust to be 1 minute after preceding event ends
            candidate_reminder_time = preceding_event.end_time + timedelta(minutes=1)
            
            # Choose the later of initial or candidate time
            adjusted_reminder_time = max(initial_reminder_storage, candidate_reminder_time)
        else:
            # No conflict, keep initial reminder time
            adjusted_reminder_time = initial_reminder_storage
        
        # Ensure final reminder time is never after current event start time
        # current_event.start_time is also in storage format (naive UTC)
        final_reminder_time = min(adjusted_reminder_time, current_event.start_time)
        
        # Convert back to timezone-aware format if the input was timezone-aware
        if initial_reminder_time.tzinfo is not None:
            final_reminder_time = final_reminder_time.replace(tzinfo=timezone.utc)
        
        return final_reminder_time
        
    except Exception as e:
        logger.error(
            f"Error adjusting reminder time for consecutive events for user {user_id}, event {current_event.id}: {e}",
            exc_info=True
        )
        raise


def calculate_reminder_time(db: Session, user_id: UUID, event: Events) -> Tuple[datetime, int]:
    """Calculate the final reminder time for an event, accounting for user preferences and consecutive events.
    
    Args:
        db: Database session
        user_id: User UUID
        event: Event to calculate reminder time for
        
    Returns:
        Tuple of (final_reminder_time, effective_preparation_time_minutes)
        
    Raises:
        Exception: If database operation fails
    """
    try:
        # Determine effective preparation time
        category = event.category if event.category else "general"
        user_preference = get_user_preference(db, user_id, category)
        
        if user_preference:
            effective_preparation_time_minutes = user_preference.preparation_time_minutes
        else:
            effective_preparation_time_minutes = _get_default_preparation_time(category)
        
        # Convert event start time to timezone-aware for consistent handling
        # Database stores naive UTC datetimes, so we convert to timezone-aware UTC
        event_start_time_aware = event.start_time.replace(tzinfo=timezone.utc)
        
        # Compute initial reminder time
        initial_reminder_time = _calculate_basic_reminder_time(
            event_start_time_aware, effective_preparation_time_minutes
        )
        
        # Adjust for consecutive events
        final_reminder_time = _adjust_for_consecutive_events(
            db, user_id, event, initial_reminder_time, effective_preparation_time_minutes
        )
        
        return final_reminder_time, effective_preparation_time_minutes
        
    except Exception as e:
        logger.error(
            f"Error calculating reminder time for user {user_id}, event {event.id}: {e}",
            exc_info=True
        )
        raise


def enqueue_reminder_delivery(reminder: ReminderSettings) -> None:
    """Placeholder function for enqueuing reminder delivery.
    
    Currently logs the scheduling intent. In future implementations,
    this will integrate with a background task system.
    
    Args:
        reminder: ReminderSettings object to be delivered
    """
    try:
        logger.info(
            f"Enqueued reminder delivery: id={reminder.id}, user_id={reminder.user_id}, "
            f"event_id={reminder.event_id}, reminder_time={reminder.reminder_time}"
        )
    except Exception as e:
        logger.error(f"Error logging reminder delivery enqueue: {e}", exc_info=True)


def schedule_reminder(
    db: Session, 
    user_id: UUID, 
    event_id: Optional[UUID], 
    calculated_reminder_time: datetime, 
    lead_time_minutes: int, 
    notification_method: str = 'in-app'
) -> ReminderSettings:
    """Create a new scheduled reminder in the database.
    
    Args:
        db: Database session
        user_id: User ID for the reminder
        event_id: Event ID (optional, can be None for non-event reminders)
        calculated_reminder_time: When the reminder should be delivered
        lead_time_minutes: Lead time in minutes
        notification_method: Method for notification (default: 'in-app')
        
    Returns:
        Created ReminderSettings object
        
    Raises:
        Exception: If database operation fails
    """
    try:
        # Normalize reminder time using storage format
        reminder_time_storage = _to_storage_datetime(calculated_reminder_time)
        
        # Create new ReminderSettings record
        reminder = ReminderSettings(
            user_id=user_id,
            event_id=event_id,
            reminder_time=reminder_time_storage,
            lead_time_minutes=lead_time_minutes,
            reminder_type='event',
            status='pending',
            notification_method=notification_method,
            is_active=True,
            reminder_metadata=None
        )
        
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        
        logger.info(f"Scheduled reminder created: id={reminder.id}, user_id={user_id}, event_id={event_id}")
        
        # Call placeholder enqueue function
        enqueue_reminder_delivery(reminder)
        
        return reminder
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error scheduling reminder for user {user_id}, event {event_id}: {e}", exc_info=True)
        raise


def cancel_scheduled_reminder(db: Session, user_id: UUID, scheduled_reminder_id: UUID) -> ReminderSettings:
    """Cancel a scheduled reminder by setting its status to 'cancelled'.
    
    Args:
        db: Database session
        user_id: User ID for ownership verification
        scheduled_reminder_id: ID of the reminder to cancel
        
    Returns:
        Updated ReminderSettings object
        
    Raises:
        ValueError: If reminder not found or access denied
        Exception: If database operation fails
    """
    try:
        # Look up the reminder with ownership check
        stmt = select(ReminderSettings).where(
            ReminderSettings.id == scheduled_reminder_id,
            ReminderSettings.user_id == user_id
        )
        
        result = db.execute(stmt)
        reminder = result.scalar_one_or_none()
        
        if reminder is None:
            raise ValueError("Scheduled reminder not found or access denied")
        
        # If already cancelled, return as-is (idempotent)
        if reminder.status == 'cancelled':
            return reminder
        
        # Update status to cancelled
        reminder.status = 'cancelled'
        reminder.is_active = False
        
        db.commit()
        db.refresh(reminder)
        
        logger.info(f"Cancelled scheduled reminder: id={scheduled_reminder_id}, user_id={user_id}")
        
        return reminder
        
    except ValueError:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling scheduled reminder {scheduled_reminder_id} for user {user_id}: {e}", exc_info=True)
        raise


def cancel_scheduled_reminders_for_event(
    db: Session, 
    user_id: UUID, 
    event_id: UUID
) -> List[ReminderSettings]:
    """Cancel all scheduled reminders for a specific event.
    
    Args:
        db: Database session
        user_id: User ID for ownership verification
        event_id: Event ID to cancel reminders for
        
    Returns:
        List of updated ReminderSettings objects
        
    Raises:
        Exception: If database operation fails
    """
    try:
        # Select all pending/failed active reminders for the event
        stmt = select(ReminderSettings).where(
            ReminderSettings.user_id == user_id,
            ReminderSettings.event_id == event_id,
            ReminderSettings.status.in_(['pending', 'failed']),
            ReminderSettings.is_active == True
        )
        
        result = db.execute(stmt)
        reminders = result.scalars().all()
        
        # Update each reminder to cancelled
        cancelled_reminders = []
        for reminder in reminders:
            reminder.status = 'cancelled'
            reminder.is_active = False
            cancelled_reminders.append(reminder)
        
        # Commit all changes at once
        if cancelled_reminders:
            db.commit()
            for reminder in cancelled_reminders:
                db.refresh(reminder)
            
            logger.info(f"Cancelled {len(cancelled_reminders)} reminders for event {event_id}, user {user_id}")
        
        return cancelled_reminders
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling reminders for event {event_id}, user {user_id}: {e}", exc_info=True)
        raise


def get_scheduled_reminders(
    db: Session, 
    user_id: UUID, 
    filters: Optional[dict] = None
) -> List[ReminderSettings]:
    """Retrieve scheduled reminders for a user with optional filters.
    
    Args:
        db: Database session
        user_id: User ID to get reminders for
        filters: Optional dict with filter criteria:
            - event_id: UUID to filter by event
            - status: str or list[str] to filter by status
            - time_range: tuple[datetime, datetime] for time range filtering
            - notification_method: str to filter by notification method
            - is_active: bool to filter by active status
        
    Returns:
        List of ReminderSettings objects ordered by reminder_time ascending
        
    Raises:
        Exception: If database operation fails
    """
    try:
        # Base query
        query = select(ReminderSettings).where(ReminderSettings.user_id == user_id)
        
        # Apply filters if provided
        if filters:
            if 'event_id' in filters and filters['event_id'] is not None:
                query = query.where(ReminderSettings.event_id == filters['event_id'])
            
            if 'status' in filters and filters['status'] is not None:
                status_filter = filters['status']
                if isinstance(status_filter, list):
                    query = query.where(ReminderSettings.status.in_(status_filter))
                else:
                    query = query.where(ReminderSettings.status == status_filter)
            
            if 'time_range' in filters and filters['time_range'] is not None:
                start_time, end_time = filters['time_range']
                start_storage = _to_storage_datetime(start_time)
                end_storage = _to_storage_datetime(end_time)
                query = query.where(
                    ReminderSettings.reminder_time >= start_storage,
                    ReminderSettings.reminder_time <= end_storage
                )
            
            if 'notification_method' in filters and filters['notification_method'] is not None:
                query = query.where(ReminderSettings.notification_method == filters['notification_method'])
            
            if 'is_active' in filters and filters['is_active'] is not None:
                query = query.where(ReminderSettings.is_active == filters['is_active'])
        
        # Order by reminder_time ascending
        query = query.order_by(ReminderSettings.reminder_time.asc())
        
        result = db.execute(query)
        return result.scalars().all()
        
    except Exception as e:
        logger.error(f"Error retrieving scheduled reminders for user {user_id}: {e}", exc_info=True)
        raise


def process_due_reminders(db: Session) -> List[ReminderSettings]:
    """Placeholder function to process due reminders.
    
    Currently queries for pending reminders that are due and logs them.
    In future implementations, this will trigger actual notification delivery.
    
    Args:
        db: Database session
        
    Returns:
        List of due ReminderSettings objects
        
    Raises:
        Exception: If database operation fails
    """
    try:
        # Query for pending reminders that are due (reminder_time <= now)
        stmt = select(ReminderSettings).where(
            ReminderSettings.status == 'pending',
            ReminderSettings.reminder_time <= func.now()
        )
        
        result = db.execute(stmt)
        due_reminders = result.scalars().all()
        
        # Log each due reminder
        for reminder in due_reminders:
            logger.info(
                f"Due reminder found: id={reminder.id}, user_id={reminder.user_id}, "
                f"event_id={reminder.event_id}, reminder_time={reminder.reminder_time}"
            )
        
        logger.info(f"Found {len(due_reminders)} due reminders")
        
        return due_reminders
        
    except Exception as e:
        logger.error(f"Error processing due reminders: {e}", exc_info=True)
        raise
