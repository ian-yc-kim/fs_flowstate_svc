"""Pydantic schemas for event-related operations."""

import uuid
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class EventFilter(BaseModel):
    """Schema for filtering events."""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    category: Optional[str] = None


class EventResponse(BaseModel):
    """Schema for event response including database fields."""
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    category: Optional[str] = None
    is_all_day: bool = False
    is_recurring: bool = False
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
    
    @model_validator(mode='before')
    @classmethod
    def map_event_metadata(cls, data):
        """Map event_metadata from ORM to metadata field."""
        if hasattr(data, '__dict__'):  # This is an ORM object
            # Create a dict from the ORM object
            data_dict = {}
            for key, value in data.__dict__.items():
                if not key.startswith('_'):  # Skip SQLAlchemy internal fields
                    data_dict[key] = value
            # Map event_metadata to metadata
            if 'event_metadata' in data_dict:
                data_dict['metadata'] = data_dict.pop('event_metadata')
            return data_dict
        elif isinstance(data, dict):
            # This is already a dict, check for event_metadata key
            if 'event_metadata' in data:
                data['metadata'] = data.pop('event_metadata')
        return data
