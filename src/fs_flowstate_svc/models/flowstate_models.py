import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ForeignKey, func, TypeDecorator
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.types import JSON

from .base import Base


class CrossDBJSON(TypeDecorator):
    """A JSON type that uses JSONB for PostgreSQL and JSON for other databases."""
    impl = JSON
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(JSON())


class Users(Base):
    __tablename__ = 'users'
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: str = Column(String, unique=True, nullable=False)
    email: str = Column(String, unique=True, nullable=False)
    password_hash: str = Column(String, nullable=False)
    password_reset_token: Optional[str] = Column(String, unique=True, nullable=True)
    password_reset_expires_at: Optional[DateTime] = Column(DateTime, nullable=True)
    created_at: DateTime = Column(DateTime, default=func.now(), nullable=False)
    updated_at: DateTime = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    events = relationship("Events", back_populates="user", cascade="all, delete-orphan")
    inbox_items = relationship("InboxItems", back_populates="user", cascade="all, delete-orphan")
    reminder_settings = relationship("ReminderSettings", back_populates="user", cascade="all, delete-orphan")
    ai_settings = relationship("AISettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Users(id={self.id}, username='{self.username}', email='{self.email}')>"


class Events(Base):
    __tablename__ = 'events'
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: UUID = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title: str = Column(String, nullable=False)
    description: Optional[str] = Column(Text, nullable=True)
    start_time: DateTime = Column(DateTime, nullable=False, index=True)
    end_time: DateTime = Column(DateTime, nullable=False, index=True)
    category: Optional[str] = Column(String, nullable=True)
    is_all_day: bool = Column(Boolean, default=False, nullable=False)
    is_recurring: bool = Column(Boolean, default=False, nullable=False)
    event_metadata: Optional[dict] = Column("metadata", CrossDBJSON, nullable=True)
    created_at: DateTime = Column(DateTime, default=func.now(), nullable=False)
    updated_at: DateTime = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    def __init__(self, **kwargs):
        # Handle event_metadata default: empty dict when not provided, preserve None when explicitly set
        if 'event_metadata' not in kwargs:
            kwargs['event_metadata'] = {}
        super().__init__(**kwargs)
    
    # Relationships
    user = relationship("Users", back_populates="events")
    reminder_settings = relationship("ReminderSettings", back_populates="event", cascade="save-update, merge")
    
    def __repr__(self) -> str:
        return f"<Events(id={self.id}, title='{self.title}', user_id={self.user_id})>"


class InboxItems(Base):
    __tablename__ = 'inbox_items'
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: UUID = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    content: str = Column(Text, nullable=False)
    category: Optional[str] = Column(String, nullable=True)
    priority: int = Column(Integer, nullable=False)
    status: str = Column(String, nullable=False)
    created_at: DateTime = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: DateTime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("Users", back_populates="inbox_items")
    
    def __repr__(self) -> str:
        return f"<InboxItems(id={self.id}, content='{self.content[:50]}...', user_id={self.user_id})>"


class ReminderSettings(Base):
    __tablename__ = 'reminder_settings'
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: UUID = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    event_id: Optional[UUID] = Column(UUID(as_uuid=True), ForeignKey('events.id', ondelete='SET NULL'), nullable=True)
    reminder_time: DateTime = Column(DateTime, nullable=False)
    lead_time_minutes: int = Column(Integer, nullable=False)
    reminder_type: str = Column(String, nullable=False)
    is_active: bool = Column(Boolean, default=True, nullable=False)
    created_at: DateTime = Column(DateTime, default=func.now(), nullable=False)
    updated_at: DateTime = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("Users", back_populates="reminder_settings")
    event = relationship("Events", back_populates="reminder_settings")
    
    def __repr__(self) -> str:
        return f"<ReminderSettings(id={self.id}, reminder_type='{self.reminder_type}', user_id={self.user_id})>"


class AISettings(Base):
    __tablename__ = 'ai_settings'
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: UUID = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    productivity_profile: dict = Column(CrossDBJSON, nullable=False)
    created_at: DateTime = Column(DateTime, default=func.now(), nullable=False)
    updated_at: DateTime = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("Users", back_populates="ai_settings")
    
    def __repr__(self) -> str:
        return f"<AISettings(id={self.id}, user_id={self.user_id})>"
