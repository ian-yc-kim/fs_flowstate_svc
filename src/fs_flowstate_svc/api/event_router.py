"""FastAPI event management endpoints."""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from fs_flowstate_svc.models.base import get_db
from fs_flowstate_svc.models.flowstate_models import Users
from fs_flowstate_svc.schemas import event_schemas
from fs_flowstate_svc.services import event_service
from fs_flowstate_svc.api.auth_router import get_current_user
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

# Create event router
event_router = APIRouter(tags=["Events"], prefix="/events")


@event_router.post("/", response_model=event_schemas.EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    event: event_schemas.EventCreate,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new event.
    
    Args:
        event: Event creation data
        current_user: Current authenticated user (injected dependency)
        db: Database session
        
    Returns:
        Created event response
        
    Raises:
        HTTPException: If validation fails or conflicts exist
    """
    try:
        created_event = event_service.create_event(db, current_user.id, event)
        return event_schemas.EventResponse.model_validate(created_event)
    except HTTPException:
        # Re-raise HTTP exceptions from service layer
        raise
    except Exception as e:
        logger.error(f"Unexpected error during event creation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@event_router.get("/{event_id}", response_model=event_schemas.EventResponse)
def get_event(
    event_id: UUID,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve a single event by ID.
    
    Args:
        event_id: Event ID to retrieve
        current_user: Current authenticated user (injected dependency)
        db: Database session
        
    Returns:
        Event response
        
    Raises:
        HTTPException: 404 if not found, 403 if not owned by user
    """
    try:
        event = event_service.get_event(db, event_id, current_user.id)
        return event_schemas.EventResponse.model_validate(event)
    except HTTPException:
        # Re-raise HTTP exceptions from service layer
        raise
    except Exception as e:
        logger.error(f"Unexpected error during event retrieval: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@event_router.get("/", response_model=List[event_schemas.EventResponse])
def get_events(
    start_date: Optional[date] = Query(None, description="Filter events starting from this date"),
    end_date: Optional[date] = Query(None, description="Filter events ending before this date"), 
    category: Optional[str] = Query(None, description="Filter events by category"),
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve events with optional filtering.
    
    Args:
        start_date: Filter events starting from this date
        end_date: Filter events ending before this date
        category: Filter events by category
        current_user: Current authenticated user (injected dependency)
        db: Database session
        
    Returns:
        List of event responses
    """
    try:
        # Build filter object
        filters = event_schemas.EventFilter(
            start_date=start_date,
            end_date=end_date,
            category=category
        )
        
        events = event_service.get_events(db, current_user.id, filters)
        return [event_schemas.EventResponse.model_validate(event) for event in events]
    except Exception as e:
        logger.error(f"Unexpected error during events retrieval: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@event_router.put("/{event_id}", response_model=event_schemas.EventResponse)
def update_event(
    event_id: UUID,
    event_update: event_schemas.EventUpdate,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing event.
    
    Args:
        event_id: Event ID to update
        event_update: Event update data
        current_user: Current authenticated user (injected dependency)
        db: Database session
        
    Returns:
        Updated event response
        
    Raises:
        HTTPException: If validation fails, conflicts exist, or access denied
    """
    try:
        updated_event = event_service.update_event(db, event_id, current_user.id, event_update)
        return event_schemas.EventResponse.model_validate(updated_event)
    except HTTPException:
        # Re-raise HTTP exceptions from service layer
        raise
    except Exception as e:
        logger.error(f"Unexpected error during event update: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@event_router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: UUID,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an event.
    
    Args:
        event_id: Event ID to delete
        current_user: Current authenticated user (injected dependency)
        db: Database session
        
    Returns:
        204 No Content on successful deletion
        
    Raises:
        HTTPException: If event not found or access denied
    """
    try:
        event_service.delete_event(db, event_id, current_user.id)
        # FastAPI automatically returns 204 No Content when no return value and status_code=204
    except HTTPException:
        # Re-raise HTTP exceptions from service layer
        raise
    except Exception as e:
        logger.error(f"Unexpected error during event deletion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
