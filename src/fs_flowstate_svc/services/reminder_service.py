"""Reminder service logic for default/user-specific preparation time retrieval and reminder calculation."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from fs_flowstate_svc.config import settings
from fs_flowstate_svc.models.flowstate_models import UserReminderPreference

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
