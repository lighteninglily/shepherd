from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import Field

from .base import BaseDBModel


class MessageRole(str, Enum):
    """Enum for message roles in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageType(str, Enum):
    """Enum for message types."""

    TEXT = "text"
    PRAYER = "prayer"
    SCRIPTURE = "scripture"
    ACTION = "action"


class ConversationStatus(str, Enum):
    """Enum for conversation status."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MessageBase(BaseDBModel):
    """Base model for chat messages."""

    role: MessageRole = MessageRole.USER
    content: str
    message_type: MessageType = MessageType.TEXT
    metadata: dict = Field(default_factory=dict)
    parent_message_id: Optional[str] = None


class MessageCreate(MessageBase):
    """Schema for creating a new message."""

    conversation_id: str


class MessageUpdate(BaseDBModel):
    """Schema for updating a message."""

    content: Optional[str] = None
    metadata: Optional[dict] = None


class MessageInDB(MessageBase):
    """Message model for database storage."""

    conversation_id: str
    user_id: str
    tokens: int = 0
    is_flagged: bool = False


class Message(MessageInDB):
    """Message model for API responses."""

    id: str
    conversation_id: str
    user_id: str


class ConversationBase(BaseDBModel):
    """Base model for conversations."""

    title: Optional[str] = None
    status: ConversationStatus = ConversationStatus.ACTIVE
    metadata: dict = Field(default_factory=dict)


class ConversationCreate(ConversationBase):
    """Schema for creating a new conversation."""

    user_id: Optional[str] = None


class ConversationUpdate(BaseDBModel):
    """Schema for updating a conversation."""

    title: Optional[str] = None
    status: Optional[ConversationStatus] = None
    metadata: Optional[dict] = None


class ConversationInDB(ConversationBase):
    """Conversation model for database storage."""

    user_id: str
    message_count: int = 0
    last_message_at: Optional[datetime] = None


class Conversation(ConversationInDB):
    """Conversation model for API responses."""

    id: str
    user_id: str


class ConversationWithMessages(Conversation):
    """Conversation model with included messages."""

    messages: List[Message] = []


class ConversationList(BaseDBModel):
    """Schema for listing conversations with pagination."""

    items: List[Conversation]
    total: int
    page: int
    page_size: int


class MessageList(BaseDBModel):
    """Schema for listing messages with pagination."""

    items: List[Message]
    total: int
    page: int
    page_size: int
    conversation_id: str
