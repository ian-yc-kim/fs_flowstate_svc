"""Reminder service logic for default/user-specific preparation time retrieval and reminder calculation."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from fs_flowstate_svc.config import settings
from fs_flowstate_svc.models.flowstate_models import UserReminderPreference, Events

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
