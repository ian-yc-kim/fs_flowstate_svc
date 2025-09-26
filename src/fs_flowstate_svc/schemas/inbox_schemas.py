"""Pydantic schemas for inbox item management operations."""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum, IntEnum
from pydantic import BaseModel, ConfigDict, Field


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
    """Schema for filtering inbox items."""
    category: Optional[InboxCategory] = None
    priority_min: Optional[InboxPriority] = None
    priority_max: Optional[InboxPriority] = None
    status: Optional[InboxStatus] = None


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
