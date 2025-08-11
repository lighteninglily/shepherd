from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# Base class for SQLAlchemy models
Base = declarative_base()


def generate_uuid():
    return str(uuid4())


class User(Base):
    """SQLAlchemy model for users."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow, nullable=True)

    # Relationships
    conversations = relationship("Conversation", back_populates="user")
    prayers = relationship("Prayer", back_populates="user")

    def __repr__(self):
        return f"<User(id='{self.id}', email='{self.email}')>"


class Conversation(Base):
    """SQLAlchemy model for conversations."""

    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    # Arbitrary metadata for conversational state (e.g., intake flags, last_intent)
    metadata_json = Column("metadata", JSON, default=dict)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Conversation(id='{self.id}', title='{self.title}')>"


class Message(Base):
    """SQLAlchemy model for messages."""

    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant' or 'system'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Optional per-message metadata (e.g., tokens, annotations)
    metadata_json = Column("metadata", JSON, default=dict)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message(id='{self.id}', role='{self.role}')>"


class Prayer(Base):
    """SQLAlchemy model for prayer entries."""

    __tablename__ = "prayers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    is_answered = Column(Boolean, default=False)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow, nullable=True)

    # Relationships
    user = relationship("User", back_populates="prayers")

    def __repr__(self):
        return f"<Prayer(id='{self.id}', title='{self.title}')>"


class UserProfile(Base):
    """SQLAlchemy model for user profiles."""

    __tablename__ = "user_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    avatar_url = Column(String(512), nullable=True)
    bio = Column(Text, nullable=True)
    preferences = Column(JSON, default=dict)

    def __repr__(self):
        return f"<UserProfile(user_id='{self.user_id}')>"


class BibleVerse(Base):
    """SQLAlchemy model for Bible verses."""

    __tablename__ = "bible_verses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    book = Column(String(50), nullable=False)
    chapter = Column(Integer, nullable=False)
    verse = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    version = Column(String(10), default="NIV")

    def __repr__(self):
        return f"<BibleVerse({self.book} {self.chapter}:{self.verse})>"


class PrayerRequest(Base):
    """SQLAlchemy model for prayer referral requests to pastoral team."""

    __tablename__ = "prayer_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    is_anonymous = Column(Boolean, default=False)
    consent_forward = Column(Boolean, default=False, nullable=False)
    # Flatten basic location fields for simple reporting; keep raw in metadata
    location_country = Column(String(100), nullable=True)
    location_region = Column(String(100), nullable=True)
    location_city = Column(String(100), nullable=True)
    # Arbitrary extra data: risk flags, contact preference, etc.
    metadata_json = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow, nullable=True)

    def __repr__(self):
        return f"<PrayerRequest(id='{self.id}', title='{self.title}', consent_forward={self.consent_forward})>"
