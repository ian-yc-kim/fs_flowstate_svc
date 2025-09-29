"""Pydantic schemas for inbox item management operations."""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum, IntEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator


class InboxCategory(str, Enum):
    """Enum for inbox item categories."""
    TODO = "TODO"
    IDEA = "IDEA"
    NOTE = "NOTE"


class InboxPriority(IntEnum):
    """Enum for inbox item priorities with integer values."""
    P1 = 1
    P2 = 2
    P3 = 3
    P4 = 4
    P5 = 5


class InboxStatus(str, Enum):
    """Enum for inbox item status."""
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    ARCHIVED = "ARCHIVED"
    DONE = "DONE"


class InboxItemBase(BaseModel):
    """Base inbox item schema with common fields."""
    content: str
    category: InboxCategory
    priority: InboxPriority
    status: InboxStatus


class InboxItemCreate(BaseModel):
    """Schema for inbox item creation."""
    content: str
    category: InboxCategory = InboxCategory.TODO
    priority: InboxPriority = InboxPriority.P3
    status: InboxStatus = InboxStatus.PENDING


class InboxItemUpdate(BaseModel):
    """Schema for inbox item updates with all fields optional."""
    content: Optional[str] = None
    category: Optional[InboxCategory] = None
    priority: Optional[InboxPriority] = None
    status: Optional[InboxStatus] = None


class InboxItemResponse(InboxItemBase):
    """Schema for inbox item response including database fields."""
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class InboxItemFilter(BaseModel):
    """Schema for filtering inbox items.

    Supports multi-select fields for categories, statuses, and priorities.
    The filter_logic field controls how different types of filters are combined (AND/OR).
    """
    categories: Optional[List[InboxCategory]] = Field(
        None,
        description="List of categories to filter by. Items matching any category in the list will be included."
    )
    statuses: Optional[List[InboxStatus]] = Field(
        None,
        description="List of statuses to filter by. Items matching any status in the list will be included."
    )
    priorities: Optional[List[InboxPriority]] = Field(
        None,
        description="List of priorities to filter by. Items matching any priority in the list will be included."
    )
    priority_min: Optional[InboxPriority] = None
    priority_max: Optional[InboxPriority] = None
    filter_logic: Optional[str] = Field(
        "AND",
        description="Logic to combine different filter types (categories, statuses, priorities, priority_min/max). Can be 'AND' or 'OR'. Defaults to 'AND'."
    )

    # Validators to support CSV strings and case-insensitive logic
    @field_validator("categories", mode="before")
    def _parse_categories(cls, v):
        try:
            if v is None:
                return None
            # accept CSV string
            if isinstance(v, str):
                s = v.strip()
                if s == "":
                    return None
                parts = [p.strip() for p in s.split(",") if p.strip()]
                return [InboxCategory(p) for p in parts]
            # accept single enum value
            if isinstance(v, InboxCategory):
                return [v]
            # accept list of strings or enums
            if isinstance(v, list):
                result = []
                for item in v:
                    if isinstance(item, str):
                        result.append(InboxCategory(item))
                    elif isinstance(item, InboxCategory):
                        result.append(item)
                return result or None
            return None
        except Exception:
            # Let pydantic raise validation error
            raise

    @field_validator("statuses", mode="before")
    def _parse_statuses(cls, v):
        try:
            if v is None:
                return None
            if isinstance(v, str):
                s = v.strip()
                if s == "":
                    return None
                parts = [p.strip() for p in s.split(",") if p.strip()]
                return [InboxStatus(p) for p in parts]
            if isinstance(v, InboxStatus):
                return [v]
            if isinstance(v, list):
                result = []
                for item in v:
                    if isinstance(item, str):
                        result.append(InboxStatus(item))
                    elif isinstance(item, InboxStatus):
                        result.append(item)
                return result or None
            return None
        except Exception:
            raise

    @field_validator("priorities", mode="before")
    def _parse_priorities(cls, v):
        try:
            if v is None:
                return None
            if isinstance(v, str):
                s = v.strip()
                if s == "":
                    return None
                parts = [p.strip() for p in s.split(",") if p.strip()]
                return [InboxPriority(int(p)) if p.isdigit() else InboxPriority(p) for p in parts]
            if isinstance(v, InboxPriority):
                return [v]
            if isinstance(v, list):
                result = []
                for item in v:
                    if isinstance(item, int):
                        result.append(InboxPriority(item))
                    elif isinstance(item, str):
                        if item.isdigit():
                            result.append(InboxPriority(int(item)))
                        else:
                            result.append(InboxPriority(item))
                    elif isinstance(item, InboxPriority):
                        result.append(item)
                return result or None
            return None
        except Exception:
            raise

    @field_validator("filter_logic", mode="before")
    def _normalize_filter_logic(cls, v):
        if v is None:
            return "AND"
        if isinstance(v, str):
            s = v.strip().upper()
            return "OR" if s == "OR" else "AND"
        return "AND"


class InboxItemsBulkUpdate(BaseModel):
    """Schema for bulk updating inbox items status."""
    item_ids: List[uuid.UUID]
    new_status: InboxStatus


class InboxItemsBulkArchive(BaseModel):
    """Schema for bulk archiving inbox items."""
    item_ids: List[uuid.UUID]


class InboxItemConvertToEvent(BaseModel):
    """Schema for converting an inbox item to a calendar event."""
    item_id: uuid.UUID = Field(..., description="The ID of the inbox item to convert.")
    start_time: datetime = Field(..., description="Start time of the new calendar event (ISO 8601 format). Example: '2023-10-27T10:00:00Z'")
    end_time: datetime = Field(..., description="End time of the new calendar event (ISO 8601 format). Example: '2023-10-27T11:00:00Z'")
    event_title: Optional[str] = Field(None, description="Optional title for the event. Defaults to inbox item content if not provided.")
    event_description: Optional[str] = Field(None, description="Optional description for the event. Defaults to inbox item content if not provided and content is short, or empty.")
    is_all_day: bool = Field(False, description="Whether the event is an all-day event.")
    is_recurring: bool = Field(False, description="Whether the event is a recurring event.")
    event_category: Optional[str] = Field(None, description="Optional category for the event. Defaults to inbox item category if not provided.")
    event_metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata for the event. The original inbox item ID will be included here automatically. Example: {'priority': 'high'}")
