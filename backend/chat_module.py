"""
CHAT MODULE - WhatsApp-level Features
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE_NOTE = "voice_note"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    STICKER = "sticker"

class MessageStatus(str, Enum):
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

class ConversationType(str, Enum):
    PRIVATE = "private"  # 1-1 match chat
    TRIP_GROUP = "trip_group"  # Trip group chat
    SUPPORT = "support"  # Customer support

class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    sender_id: str
    message_type: MessageType = MessageType.TEXT
    content: str = ""
    media_url: Optional[str] = None
    media_thumbnail: Optional[str] = None
    media_duration: Optional[int] = None  # For audio/video in seconds
    media_size: Optional[int] = None  # In bytes
    reply_to_id: Optional[str] = None
    forwarded_from: Optional[str] = None
    status: MessageStatus = MessageStatus.SENDING
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    read_by: List[str] = []  # For group chats
    metadata: Dict[str, Any] = {}
    is_deleted: bool = False
    deleted_for: List[str] = []  # Delete for specific users
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Conversation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: ConversationType = ConversationType.PRIVATE
    participants: List[str]
    trip_id: Optional[str] = None  # For trip groups
    name: Optional[str] = None  # For groups
    image: Optional[str] = None
    admins: List[str] = []  # For groups
    created_by: str
    last_message_id: Optional[str] = None
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    unread_counts: Dict[str, int] = {}  # user_id: count
    is_muted_by: List[str] = []
    is_archived_by: List[str] = []
    is_pinned_by: List[str] = []
    settings: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class UserPresence(BaseModel):
    user_id: str
    is_online: bool = False
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    is_typing_in: Optional[str] = None  # conversation_id
    typing_started_at: Optional[datetime] = None
    device_token: Optional[str] = None  # For push notifications
    platform: Optional[str] = None  # ios, android, web

class PushNotification(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    title: str
    body: str
    data: Dict[str, Any] = {}
    notification_type: str  # message, booking, trip, match
    is_read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TypingIndicator(BaseModel):
    conversation_id: str
    user_id: str
    is_typing: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ReadReceipt(BaseModel):
    conversation_id: str
    message_id: str
    user_id: str
    read_at: datetime = Field(default_factory=datetime.utcnow)
