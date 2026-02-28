"""
CHAT ROUTES - Production Hardened
Security: Rate limiting, file validation, XSS prevention, access control
"""

from fastapi import APIRouter, HTTPException, Depends, Header, UploadFile, File
from typing import Optional, List
from datetime import datetime, timedelta
import os
import re
import html
import cloudinary
import cloudinary.uploader
from chat_module import *

chat_router = APIRouter(prefix="/chat", tags=["chat"])

# ===================
# SECURITY CONSTANTS
# ===================
MAX_MESSAGE_LENGTH = 4000
MAX_FILE_SIZE_MB = 25
MAX_IMAGE_SIZE_MB = 10
MAX_VIDEO_SIZE_MB = 50
MAX_MESSAGES_PER_MINUTE = 30
MAX_TYPING_UPDATES_PER_MINUTE = 10
MAX_PRESENCE_UPDATES_PER_MINUTE = 5

ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
ALLOWED_VIDEO_TYPES = {'video/mp4', 'video/webm', 'video/quicktime'}
ALLOWED_AUDIO_TYPES = {'audio/mpeg', 'audio/mp4', 'audio/wav', 'audio/ogg', 'audio/webm'}
ALLOWED_DOC_TYPES = {'application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'}

# ===================
# SECURITY HELPERS
# ===================
def sanitize_message(content: str) -> str:
    """Sanitize message content to prevent XSS"""
    if not content:
        return ""
    # HTML escape
    sanitized = html.escape(content)
    # Remove any potential script injection patterns
    sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
    return sanitized[:MAX_MESSAGE_LENGTH]

def validate_file_type(content_type: str, message_type: str) -> bool:
    """Validate file type against allowed types"""
    if message_type in ['image']:
        return content_type in ALLOWED_IMAGE_TYPES
    elif message_type in ['video']:
        return content_type in ALLOWED_VIDEO_TYPES
    elif message_type in ['audio', 'voice_note']:
        return content_type in ALLOWED_AUDIO_TYPES
    elif message_type in ['document']:
        return content_type in ALLOWED_DOC_TYPES
    return False

def get_max_file_size(message_type: str) -> int:
    """Get max file size in bytes for message type"""
    if message_type == 'image':
        return MAX_IMAGE_SIZE_MB * 1024 * 1024
    elif message_type == 'video':
        return MAX_VIDEO_SIZE_MB * 1024 * 1024
    return MAX_FILE_SIZE_MB * 1024 * 1024

async def check_rate_limit(db, user_id: str, action: str, limit: int, window_minutes: int = 1) -> bool:
    """Check rate limit for user action"""
    window_start = datetime.utcnow() - timedelta(minutes=window_minutes)
    count = await db.rate_limits.count_documents({
        "user_id": user_id,
        "action": action,
        "timestamp": {"$gte": window_start}
    })
    return count < limit

async def record_rate_limit(db, user_id: str, action: str):
    """Record rate limit event"""
    await db.rate_limits.insert_one({
        "user_id": user_id,
        "action": action,
        "timestamp": datetime.utcnow()
    })
    # Cleanup old entries
    await db.rate_limits.delete_many({
        "timestamp": {"$lt": datetime.utcnow() - timedelta(hours=1)}
    })

async def verify_conversation_access(db, conversation_id: str, user_id: str) -> dict:
    """Verify user has access to conversation"""
    conversation = await db.conversations.find_one({
        "id": conversation_id,
        "participants": user_id
    })
    if not conversation:
        raise HTTPException(status_code=403, detail="Access denied to this conversation")
    return conversation

async def get_current_user_chat(authorization: str = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from server import verify_jwt_token
    user_id = verify_jwt_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id

# ===================
# CONVERSATION ENDPOINTS
# ===================
@chat_router.get("/conversations")
async def get_conversations(
    page: int = 1,
    limit: int = 20,
    current_user: str = Depends(get_current_user_chat)
):
    """Get user's conversations with pagination"""
    from server import db
    
    # Enforce pagination limits
    limit = min(limit, 50)
    page = max(page, 1)
    
    query = {
        "participants": current_user,
        "is_archived_by": {"$ne": current_user}
    }
    
    total = await db.conversations.count_documents(query)
    skip = (page - 1) * limit
    
    conversations = await db.conversations.find(query).sort(
        "last_message_at", -1
    ).skip(skip).limit(limit).to_list(length=limit)
    
    # Get participant details (sanitized)
    for conv in conversations:
        participant_ids = [p for p in conv['participants'] if p != current_user]
        participants = await db.users.find(
            {"id": {"$in": participant_ids}}
        ).to_list(length=len(participant_ids))
        conv['participants_info'] = [
            {"id": p['id'], "name": html.escape(p.get('full_name', 'Unknown')), "image": p.get('profile_image')}
            for p in participants
        ]
        conv['unread_count'] = conv.get('unread_counts', {}).get(current_user, 0)
        # Remove sensitive fields
        conv.pop('_id', None)
    
    return {
        "conversations": conversations,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": (skip + len(conversations)) < total
    }

@chat_router.post("/conversation/create")
async def create_conversation(
    participant_id: Optional[str] = None,
    trip_id: Optional[str] = None,
    name: Optional[str] = None,
    current_user: str = Depends(get_current_user_chat)
):
    """Create new conversation with validation"""
    from server import db
    
    if trip_id:
        trip = await db.trips.find_one({"id": trip_id})
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        
        # Check if user is authorized for this trip
        trip_members = trip.get('members', [trip.get('creator_id')])
        if current_user not in trip_members and current_user != trip.get('creator_id'):
            raise HTTPException(status_code=403, detail="Not a member of this trip")
        
        existing = await db.conversations.find_one({"trip_id": trip_id})
        if existing:
            return {"conversation_id": existing['id'], "existing": True}
        
        participants = trip_members.copy()
        if current_user not in participants:
            participants.append(current_user)
        
        conversation = Conversation(
            type=ConversationType.TRIP_GROUP,
            participants=participants,
            trip_id=trip_id,
            name=sanitize_message(name) if name else f"Trip to {html.escape(trip.get('destination', 'Unknown'))}",
            admins=[trip.get('creator_id')],
            created_by=current_user
        )
    else:
        if not participant_id:
            raise HTTPException(status_code=400, detail="participant_id required")
        
        # Verify participant exists
        participant = await db.users.find_one({"id": participant_id})
        if not participant:
            raise HTTPException(status_code=404, detail="Participant not found")
        
        # Prevent self-chat
        if participant_id == current_user:
            raise HTTPException(status_code=400, detail="Cannot create conversation with yourself")
        
        existing = await db.conversations.find_one({
            "type": ConversationType.PRIVATE.value,
            "participants": {"$all": [current_user, participant_id]}
        })
        if existing:
            return {"conversation_id": existing['id'], "existing": True}
        
        conversation = Conversation(
            type=ConversationType.PRIVATE,
            participants=[current_user, participant_id],
            created_by=current_user
        )
    
    await db.conversations.insert_one(conversation.model_dump())
    return {"conversation_id": conversation.id, "existing": False}

@chat_router.get("/messages/{conversation_id}")
async def get_messages(
    conversation_id: str,
    before_id: Optional[str] = None,
    limit: int = 50,
    current_user: str = Depends(get_current_user_chat)
):
    """Get messages with access control and pagination"""
    from server import db
    
    # Verify access
    await verify_conversation_access(db, conversation_id, current_user)
    
    # Enforce limits
    limit = min(limit, 100)
    
    query = {
        "conversation_id": conversation_id,
        "is_deleted": False,
        "deleted_for": {"$ne": current_user}
    }
    
    if before_id:
        before_msg = await db.messages.find_one({"id": before_id})
        if before_msg:
            query["created_at"] = {"$lt": before_msg['created_at']}
    
    messages = await db.messages.find(query).sort(
        "created_at", -1
    ).limit(limit).to_list(length=limit)
    
    # Mark as read
    unread_ids = [
        m['id'] for m in messages
        if m['sender_id'] != current_user and current_user not in m.get('read_by', [])
    ]
    
    if unread_ids:
        await db.messages.update_many(
            {"id": {"$in": unread_ids}},
            {
                "$addToSet": {"read_by": current_user},
                "$set": {"status": MessageStatus.READ.value, "read_at": datetime.utcnow()}
            }
        )
        await db.conversations.update_one(
            {"id": conversation_id},
            {"$set": {f"unread_counts.{current_user}": 0}}
        )
    
    # Clean messages
    for msg in messages:
        msg.pop('_id', None)
    
    return {
        "messages": list(reversed(messages)),
        "has_more": len(messages) == limit
    }

@chat_router.post("/message/send")
async def send_message(
    conversation_id: str,
    content: str,
    message_type: str = "text",
    reply_to_id: Optional[str] = None,
    current_user: str = Depends(get_current_user_chat)
):
    """Send text message with rate limiting and sanitization"""
    from server import db, sio
    
    # Rate limit check
    if not await check_rate_limit(db, current_user, "send_message", MAX_MESSAGES_PER_MINUTE):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please slow down.")
    
    # Verify access
    conversation = await verify_conversation_access(db, conversation_id, current_user)
    
    # Sanitize content
    sanitized_content = sanitize_message(content)
    if not sanitized_content.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    message = Message(
        conversation_id=conversation_id,
        sender_id=current_user,
        message_type=MessageType(message_type),
        content=sanitized_content,
        reply_to_id=reply_to_id,
        status=MessageStatus.SENT
    )
    
    await db.messages.insert_one(message.model_dump())
    await record_rate_limit(db, current_user, "send_message")
    
    preview = sanitized_content[:50] + "..." if len(sanitized_content) > 50 else sanitized_content
    
    unread_updates = {
        f"unread_counts.{p}": 1
        for p in conversation['participants']
        if p != current_user
    }
    
    await db.conversations.update_one(
        {"id": conversation_id},
        {
            "$set": {
                "last_message_id": message.id,
                "last_message_at": message.created_at,
                "last_message_preview": preview,
                "updated_at": datetime.utcnow()
            },
            "$inc": unread_updates
        }
    )
    
    try:
        await sio.emit('new_message', message.model_dump(), room=conversation_id)
    except:
        pass
    
    # Push notifications
    sender = await db.users.find_one({"id": current_user})
    sender_name = html.escape(sender.get('full_name', 'Someone')) if sender else "Someone"
    
    for participant in conversation['participants']:
        if participant != current_user:
            presence = await db.user_presence.find_one({"user_id": participant})
            if not presence or not presence.get('is_online'):
                notification = PushNotification(
                    user_id=participant,
                    title=sender_name,
                    body=preview,
                    data={"conversation_id": conversation_id, "message_id": message.id},
                    notification_type="message"
                )
                await db.push_notifications.insert_one(notification.model_dump())
    
    return {"message_id": message.id, "status": "sent"}

@chat_router.post("/message/media")
async def send_media_message(
    conversation_id: str,
    message_type: str,
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user_chat)
):
    """Send media message with file validation"""
    from server import db, sio
    
    # Rate limit
    if not await check_rate_limit(db, current_user, "send_media", 10):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Verify access
    conversation = await verify_conversation_access(db, conversation_id, current_user)
    
    # Validate file type
    content_type = file.content_type or 'application/octet-stream'
    if not validate_file_type(content_type, message_type):
        raise HTTPException(status_code=400, detail=f"Invalid file type: {content_type}")
    
    # Read and validate file size
    content = await file.read()
    max_size = get_max_file_size(message_type)
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {max_size // (1024*1024)}MB")
    
    # Upload to Cloudinary
    try:
        resource_type = "auto"
        if message_type in ["voice_note", "audio"]:
            resource_type = "video"
        
        result = cloudinary.uploader.upload(
            content,
            resource_type=resource_type,
            folder=f"chat/{conversation_id}",
            allowed_formats=['jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'webm', 'mp3', 'wav', 'pdf'] if message_type != 'document' else None
        )
        
        media_url = result['secure_url']
        media_size = result.get('bytes', len(content))
        media_duration = result.get('duration', 0)
        thumbnail = result.get('thumbnail_url')
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Upload failed")
    
    message = Message(
        conversation_id=conversation_id,
        sender_id=current_user,
        message_type=MessageType(message_type),
        content=html.escape(file.filename or "")[:255],
        media_url=media_url,
        media_thumbnail=thumbnail,
        media_duration=int(media_duration) if media_duration else None,
        media_size=media_size,
        status=MessageStatus.SENT
    )
    
    await db.messages.insert_one(message.model_dump())
    await record_rate_limit(db, current_user, "send_media")
    
    type_labels = {
        "image": "📷 Photo",
        "video": "🎥 Video",
        "audio": "🎵 Audio",
        "voice_note": "🎤 Voice message",
        "document": "📄 Document"
    }
    preview = type_labels.get(message_type, "📎 Attachment")
    
    await db.conversations.update_one(
        {"id": conversation_id},
        {"$set": {
            "last_message_id": message.id,
            "last_message_at": message.created_at,
            "last_message_preview": preview
        }}
    )
    
    try:
        await sio.emit('new_message', message.model_dump(), room=conversation_id)
    except:
        pass
    
    return {"message_id": message.id, "media_url": media_url}

@chat_router.post("/typing")
async def update_typing_status(
    conversation_id: str,
    is_typing: bool,
    current_user: str = Depends(get_current_user_chat)
):
    """Update typing indicator with rate limiting"""
    from server import db, sio
    
    # Rate limit typing updates
    if not await check_rate_limit(db, current_user, "typing", MAX_TYPING_UPDATES_PER_MINUTE):
        return {"status": "rate_limited"}
    
    # Verify access
    await verify_conversation_access(db, conversation_id, current_user)
    
    await db.user_presence.update_one(
        {"user_id": current_user},
        {
            "$set": {
                "is_typing_in": conversation_id if is_typing else None,
                "typing_started_at": datetime.utcnow() if is_typing else None
            }
        },
        upsert=True
    )
    await record_rate_limit(db, current_user, "typing")
    
    try:
        await sio.emit('typing', {
            "conversation_id": conversation_id,
            "user_id": current_user,
            "is_typing": is_typing
        }, room=conversation_id)
    except:
        pass
    
    return {"status": "ok"}

@chat_router.post("/read-receipt")
async def send_read_receipt(
    conversation_id: str,
    message_ids: List[str],
    current_user: str = Depends(get_current_user_chat)
):
    """Mark messages as read with access control"""
    from server import db, sio
    
    # Verify access
    await verify_conversation_access(db, conversation_id, current_user)
    
    # Limit batch size
    message_ids = message_ids[:100]
    
    await db.messages.update_many(
        {"id": {"$in": message_ids}, "conversation_id": conversation_id},
        {
            "$addToSet": {"read_by": current_user},
            "$set": {"status": MessageStatus.READ.value, "read_at": datetime.utcnow()}
        }
    )
    
    await db.conversations.update_one(
        {"id": conversation_id},
        {"$set": {f"unread_counts.{current_user}": 0}}
    )
    
    try:
        await sio.emit('read_receipt', {
            "conversation_id": conversation_id,
            "user_id": current_user,
            "message_ids": message_ids
        }, room=conversation_id)
    except:
        pass
    
    return {"status": "ok"}

@chat_router.post("/presence")
async def update_presence(
    is_online: bool,
    device_token: Optional[str] = None,
    platform: Optional[str] = None,
    current_user: str = Depends(get_current_user_chat)
):
    """Update presence with rate limiting"""
    from server import db, sio
    
    # Rate limit presence updates
    if not await check_rate_limit(db, current_user, "presence", MAX_PRESENCE_UPDATES_PER_MINUTE):
        return {"status": "rate_limited"}
    
    await db.user_presence.update_one(
        {"user_id": current_user},
        {
            "$set": {
                "is_online": is_online,
                "last_seen": datetime.utcnow(),
                "device_token": device_token[:500] if device_token else None,
                "platform": platform[:20] if platform else None
            }
        },
        upsert=True
    )
    await record_rate_limit(db, current_user, "presence")
    
    # Don't broadcast presence to everyone - only to user's conversations
    conversations = await db.conversations.find(
        {"participants": current_user}
    ).to_list(length=100)
    
    for conv in conversations:
        try:
            await sio.emit('presence', {
                "user_id": current_user,
                "is_online": is_online,
                "last_seen": datetime.utcnow().isoformat()
            }, room=conv['id'])
        except:
            pass
    
    return {"status": "ok"}

@chat_router.get("/presence/{user_id}")
async def get_presence(
    user_id: str,
    current_user: str = Depends(get_current_user_chat)
):
    """Get user's presence (only if they share a conversation)"""
    from server import db
    
    # Check if users share a conversation
    shared_conversation = await db.conversations.find_one({
        "participants": {"$all": [current_user, user_id]}
    })
    
    if not shared_conversation:
        raise HTTPException(status_code=403, detail="Cannot view this user's presence")
    
    presence = await db.user_presence.find_one({"user_id": user_id})
    
    if not presence:
        return {"is_online": False, "last_seen": None}
    
    return {
        "is_online": presence.get('is_online', False),
        "last_seen": presence.get('last_seen')
    }

@chat_router.get("/notifications")
async def get_notifications(
    page: int = 1,
    limit: int = 20,
    current_user: str = Depends(get_current_user_chat)
):
    """Get push notifications with pagination"""
    from server import db
    
    limit = min(limit, 50)
    page = max(page, 1)
    
    query = {"user_id": current_user}
    total = await db.push_notifications.count_documents(query)
    skip = (page - 1) * limit
    
    notifications = await db.push_notifications.find(query).sort(
        "created_at", -1
    ).skip(skip).limit(limit).to_list(length=limit)
    
    for notif in notifications:
        notif.pop('_id', None)
    
    unread = await db.push_notifications.count_documents({
        "user_id": current_user,
        "is_read": False
    })
    
    return {
        "notifications": notifications,
        "total": total,
        "unread": unread,
        "page": page
    }

@chat_router.delete("/message/{message_id}")
async def delete_message(
    message_id: str,
    for_everyone: bool = False,
    current_user: str = Depends(get_current_user_chat)
):
    """Delete message with ownership validation"""
    from server import db, sio
    
    message = await db.messages.find_one({"id": message_id})
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Verify access to conversation
    await verify_conversation_access(db, message['conversation_id'], current_user)
    
    if for_everyone:
        # Only sender can delete for everyone
        if message['sender_id'] != current_user:
            raise HTTPException(status_code=403, detail="Only sender can delete for everyone")
        
        # Time limit check
        msg_time = message['created_at']
        if isinstance(msg_time, str):
            msg_time = datetime.fromisoformat(msg_time)
        
        if datetime.utcnow() - msg_time > timedelta(hours=1):
            raise HTTPException(status_code=400, detail="Can only delete for everyone within 1 hour")
        
        await db.messages.update_one(
            {"id": message_id},
            {"$set": {"is_deleted": True, "content": "This message was deleted", "media_url": None}}
        )
        
        try:
            await sio.emit('message_deleted', {
                "message_id": message_id,
                "conversation_id": message['conversation_id'],
                "for_everyone": True
            }, room=message['conversation_id'])
        except:
            pass
    else:
        await db.messages.update_one(
            {"id": message_id},
            {"$addToSet": {"deleted_for": current_user}}
        )
    
    return {"status": "deleted"}
