"""FastAPI inbox management endpoints."""

import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from fs_flowstate_svc.models.base import get_db
from fs_flowstate_svc.models.flowstate_models import Users
from fs_flowstate_svc.schemas import inbox_schemas, event_schemas
from fs_flowstate_svc.services import inbox_service, user_service

logger = logging.getLogger(__name__)

# Create inbox router
inbox_router = APIRouter(prefix="/inbox", tags=["Inbox"])

# Security scheme for bearer token
security = HTTPBearer()


def get_current_user_dep(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> Users:
    """FastAPI dependency to get current user from JWT token.
    
    Args:
        credentials: HTTP Bearer token credentials
        db: Database session
        
    Returns:
        Current user object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    return user_service.get_current_user(db, credentials.credentials)


@inbox_router.post("/", response_model=inbox_schemas.InboxItemResponse, status_code=status.HTTP_201_CREATED)
def create_inbox_item(
    item: inbox_schemas.InboxItemCreate,
    current_user: Users = Depends(get_current_user_dep),
    db: Session = Depends(get_db)
):
    """Create a new inbox item.
    
    Args:
        item: Inbox item creation data
        current_user: Current authenticated user (injected dependency)
        db: Database session
        
    Returns:
        Created inbox item response
        
    Raises:
        HTTPException: If validation fails
    """
    try:
        created_item = inbox_service.create_inbox_item(db, current_user.id, item)
        return inbox_schemas.InboxItemResponse.model_validate(created_item)
    except HTTPException:
        # Re-raise HTTP exceptions from service layer
        raise
    except Exception as e:
        logger.error(f"Unexpected error during inbox item creation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@inbox_router.get("/{item_id}", response_model=inbox_schemas.InboxItemResponse)
def get_inbox_item(
    item_id: uuid.UUID,
    current_user: Users = Depends(get_current_user_dep),
    db: Session = Depends(get_db)
):
    """Retrieve a single inbox item by ID.
    
    Args:
        item_id: Inbox item ID to retrieve
        current_user: Current authenticated user (injected dependency)
        db: Database session
        
    Returns:
        Inbox item response
        
    Raises:
        HTTPException: 404 if not found or not owned by user
    """
    try:
        item = inbox_service.get_inbox_item(db, current_user.id, item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inbox item not found or not owned"
            )
        return inbox_schemas.InboxItemResponse.model_validate(item)
    except HTTPException:
        # Re-raise HTTP exceptions from service layer
        raise
    except Exception as e:
        logger.error(f"Unexpected error during inbox item retrieval: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@inbox_router.get("/", response_model=List[inbox_schemas.InboxItemResponse])
def list_inbox_items(
    request: Request,
    filters: inbox_schemas.InboxItemFilter = Depends(),
    skip: int = 0,
    limit: int = 100,
    current_user: Users = Depends(get_current_user_dep),
    db: Session = Depends(get_db)
):
    """Retrieve inbox items with optional filtering.

    Note: Accepts multi-select query params as CSV (e.g., categories=TODO,IDEA).
    If FastAPI doesn't populate the Pydantic fields as expected from query params,
    we attempt to normalize them from raw query params here before calling the service.
    Also accept legacy singular params 'category' and 'status' for backward compatibility.
    """
    try:
        # Attempt to normalize query params into the filters object when needed.
        # This provides resilience for different ways FastAPI may provide the values.
        try:
            qs = request.query_params
            # Helper to parse CSV into enum list using the same logic as schemas validators
            def _parse_csv_enum_list(raw: str, enum_cls):
                if raw is None:
                    return None
                s = raw.strip()
                if s == "":
                    return None
                parts = [p.strip() for p in s.split(",") if p.strip()]
                result = []
                for p in parts:
                    try:
                        # allow numeric priorities
                        if issubclass(enum_cls, int):
                            # Not typical; kept for safety
                            result.append(enum_cls(int(p)))
                        else:
                            result.append(enum_cls(p))
                    except Exception:
                        # try numeric conversion for priority-like enums
                        try:
                            result.append(enum_cls(int(p)))
                        except Exception:
                            raise
                return result or None

            # Only override if Pydantic did not parse them
            if not getattr(filters, "categories", None) and "categories" in qs:
                parsed = _parse_csv_enum_list(qs.get("categories"), inbox_schemas.InboxCategory)
                filters.categories = parsed

            # Back-compat: accept singular 'category' param
            if not getattr(filters, "categories", None) and "category" in qs:
                raw_c = qs.get("category")
                if raw_c is not None and raw_c.strip() != "":
                    try:
                        filters.categories = [inbox_schemas.InboxCategory(raw_c.strip())]
                    except Exception:
                        # fallback to parsing CSV
                        parsed = _parse_csv_enum_list(raw_c, inbox_schemas.InboxCategory)
                        filters.categories = parsed

            if not getattr(filters, "statuses", None) and "statuses" in qs:
                parsed = _parse_csv_enum_list(qs.get("statuses"), inbox_schemas.InboxStatus)
                filters.statuses = parsed

            # Back-compat: accept singular 'status' param
            if not getattr(filters, "statuses", None) and "status" in qs:
                raw_s = qs.get("status")
                if raw_s is not None and raw_s.strip() != "":
                    try:
                        filters.statuses = [inbox_schemas.InboxStatus(raw_s.strip())]
                    except Exception:
                        parsed = _parse_csv_enum_list(raw_s, inbox_schemas.InboxStatus)
                        filters.statuses = parsed

            if not getattr(filters, "priorities", None) and "priorities" in qs:
                # priorities are numeric or enum names
                raw = qs.get("priorities")
                if raw is not None:
                    parts = [p.strip() for p in raw.split(",") if p.strip()]
                    parsed = []
                    for p in parts:
                        if p.isdigit():
                            parsed.append(inbox_schemas.InboxPriority(int(p)))
                        else:
                            parsed.append(inbox_schemas.InboxPriority(p))
                    filters.priorities = parsed or None

            # Back-compat: accept singular 'priority' param
            if not getattr(filters, "priorities", None) and "priority" in qs:
                raw = qs.get("priority")
                if raw is not None and raw.strip() != "":
                    parts = [p.strip() for p in raw.split(",") if p.strip()]
                    parsed = []
                    for p in parts:
                        if p.isdigit():
                            parsed.append(inbox_schemas.InboxPriority(int(p)))
                        else:
                            parsed.append(inbox_schemas.InboxPriority(p))
                    filters.priorities = parsed or None

            # Normalize filter_logic if provided raw
            if (filters.filter_logic is None or filters.filter_logic == "AND") and "filter_logic" in qs:
                raw_logic = qs.get("filter_logic")
                if raw_logic:
                    filters.filter_logic = "OR" if raw_logic.strip().upper() == "OR" else "AND"
        except Exception as e:
            logger.error(f"Error normalizing query params for filters: {e}", exc_info=True)

        items = inbox_service.get_inbox_items(db, current_user.id, filters, skip, limit)
        return [inbox_schemas.InboxItemResponse.model_validate(item) for item in items]
    except Exception as e:
        logger.error(f"Unexpected error during inbox items retrieval: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@inbox_router.put("/{item_id}", response_model=inbox_schemas.InboxItemResponse)
def update_inbox_item(
    item_id: uuid.UUID,
    item_update: inbox_schemas.InboxItemUpdate,
    current_user: Users = Depends(get_current_user_dep),
    db: Session = Depends(get_db)
):
    """Update an existing inbox item.
    
    Args:
        item_id: Inbox item ID to update
        item_update: Inbox item update data
        current_user: Current authenticated user (injected dependency)
        db: Database session
        
    Returns:
        Updated inbox item response
        
    Raises:
        HTTPException: If validation fails, item not found, or access denied
    """
    try:
        updated_item = inbox_service.update_inbox_item(db, current_user.id, item_id, item_update)
        return inbox_schemas.InboxItemResponse.model_validate(updated_item)
    except HTTPException:
        # Re-raise HTTP exceptions from service layer
        raise
    except Exception as e:
        logger.error(f"Unexpected error during inbox item update: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@inbox_router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inbox_item(
    item_id: uuid.UUID,
    current_user: Users = Depends(get_current_user_dep),
    db: Session = Depends(get_db)
):
    """Delete an inbox item.
    
    Args:
        item_id: Inbox item ID to delete
        current_user: Current authenticated user (injected dependency)
        db: Database session
        
    Returns:
        204 No Content on successful deletion
        
    Raises:
        HTTPException: If item not found or access denied
    """
    try:
        deleted = inbox_service.delete_inbox_item(db, current_user.id, item_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inbox item not found or not owned"
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        # Re-raise HTTP exceptions from service layer
        raise
    except Exception as e:
        logger.error(f"Unexpected error during inbox item deletion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@inbox_router.post("/bulk/status")
def bulk_update_status(
    payload: inbox_schemas.InboxItemsBulkUpdate,
    current_user: Users = Depends(get_current_user_dep),
    db: Session = Depends(get_db)
):
    """Bulk update inbox items status.
    
    Args:
        payload: Bulk update payload with item IDs and new status
        current_user: Current authenticated user (injected dependency)
        db: Database session
        
    Returns:
        Message with number of items updated
    """
    try:
        count = inbox_service.bulk_update_inbox_item_status(
            db, current_user.id, payload.item_ids, payload.new_status
        )
        return {"message": f"{count} items updated"}
    except HTTPException:
        # Re-raise HTTP exceptions from service layer
        raise
    except Exception as e:
        logger.error(f"Unexpected error during bulk status update: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@inbox_router.post("/bulk/archive")
def bulk_archive_items(
    payload: inbox_schemas.InboxItemsBulkArchive,
    current_user: Users = Depends(get_current_user_dep),
    db: Session = Depends(get_db)
):
    """Bulk archive inbox items.
    
    Args:
        payload: Bulk archive payload with item IDs
        current_user: Current authenticated user (injected dependency)
        db: Database session
        
    Returns:
        Message with number of items archived
    """
    try:
        count = inbox_service.bulk_archive_inbox_items(db, current_user.id, payload.item_ids)
        return {"message": f"{count} items archived"}
    except HTTPException:
        # Re-raise HTTP exceptions from service layer
        raise
    except Exception as e:
        logger.error(f"Unexpected error during bulk archive: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@inbox_router.post("/convert_to_event", response_model=event_schemas.EventResponse, status_code=status.HTTP_201_CREATED)
def convert_inbox_item_to_event(
    conversion_data: inbox_schemas.InboxItemConvertToEvent,
    current_user: Users = Depends(get_current_user_dep),
    db: Session = Depends(get_db)
):
    """Convert an existing inbox item into a calendar event.
    
    This endpoint allows users to convert inbox items into scheduled events.
    The original inbox item will be marked as SCHEDULED upon successful conversion.
    
    Args:
        conversion_data: Conversion request data including item ID and event details
        current_user: Current authenticated user (injected dependency)
        db: Database session
        
    Returns:
        Created event response with 201 Created status
        
    Raises:
        HTTPException: 
            - 400 Bad Request: If validation fails (e.g., invalid times)
            - 404 Not Found: If inbox item not found or not owned by user
            - 409 Conflict: If event time conflicts with existing events
            - 500 Internal Server Error: If database operation fails
    """
    try:
        created_event = inbox_service.convert_inbox_item_to_event(db, current_user.id, conversion_data)
        return event_schemas.EventResponse.model_validate(created_event)
    except HTTPException:
        # Re-raise HTTP exceptions from service layer (400, 404, 409)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during inbox item to event conversion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
