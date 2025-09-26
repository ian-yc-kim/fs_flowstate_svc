"""Pydantic schemas for event-related operations."""

import uuid
from datetime import datetime, date
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class EventBase(BaseModel):
    """Base event schema with common fields."""
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    category: Optional[str] = None
    is_all_day: bool = False
    is_recurring: bool = False
    metadata: Optional[Dict[str, Any]] = None


class EventCreate(EventBase):
    """Schema for event creation with required fields."""
    # title, start_time, end_time are required from EventBase
    pass


class EventUpdate(BaseModel):
    """Schema for event updates with all fields optional."""
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    category: Optional[str] = None
    is_all_day: Optional[bool] = None
    is_recurring: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class EventResponse(EventBase):
    """Schema for event response including database fields."""
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class EventFilter(BaseModel):
    """Schema for filtering events."""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    category: Optional[str] = None
