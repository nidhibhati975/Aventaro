"""
CHAT ROUTES - Full Featured
"""

from fastapi import APIRouter, HTTPException, Depends, Header, UploadFile, File
from typing import Optional, List
from datetime import datetime, timedelta
import os
import cloudinary
import cloudinary.uploader
from chat_module import *

chat_router = APIRouter(prefix="/chat", tags=["chat"])

async def get_current_user_chat(authorization: str = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from server import verify_jwt_token
    user_id = verify_jwt_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id

@chat_router.get("/conversations")
async def get_conversations(
    page: int = 1,
    limit: int = 20,
    current_user: str = Depends(get_current_user_chat)
):
    """Get user's conversations"""
    from server import db
    
    query = {
        "participants": current_user,
        f"is_archived_by": {"$ne": current_user}
    }
    
    total = await db.conversations.count_documents(query)
    skip = (page - 1) * limit
    
    conversations = await db.conversations.find(query).sort(
        "last_message_at", -1
    ).skip(skip).limit(limit).to_list(length=limit)
    
    # Get participant details
    for conv in conversations:
        participant_ids = [p for p in conv['participants'] if p != current_user]
        participants = await db.users.find(
            {"id": {"$in": participant_ids}}
        ).to_list(length=len(participant_ids))
        conv['participants_info'] = [
            {"id": p['id'], "name": p['full_name'], "image": p.get('profile_image')}
            for p in participants
        ]
        conv['unread_count'] = conv.get('unread_counts', {}).get(current_user, 0)
    
    return {
        "conversations": conversations,
        "total": total,
        "page": page,
        "has_more": (skip + len(conversations)) < total
    }

@chat_router.post("/conversation/create")
async def create_conversation(
    participant_id: Optional[str] = None,
    trip_id: Optional[str] = None,
    name: Optional[str] = None,
    current_user: str = Depends(get_current_user_chat)
):
    """Create new conversation (private or trip group)"""
    from server import db
    
    if trip_id:
        # Trip group chat
        trip = await db.trips.find_one({"id": trip_id})
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        
        # Check if group already exists
        existing = await db.conversations.find_one({"trip_id": trip_id})
        if existing:
            return {"conversation_id": existing['id'], "existing": True}
        
        participants = trip.get('members', [trip['creator_id']])
        if current_user not in participants:
            participants.append(current_user)
        
        conversation = Conversation(
            type=ConversationType.TRIP_GROUP,
            participants=participants,
            trip_id=trip_id,
            name=name or f"Trip to {trip['destination']}",
            admins=[trip['creator_id']],
            created_by=current_user
        )
    else:
        # Private chat
        if not participant_id:
            raise HTTPException(status_code=400, detail="participant_id required")
        
        # Check if private chat exists
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
    """Get messages in conversation"""
    from server import db
    
    # Verify user is participant
    conversation = await db.conversations.find_one({
        "id": conversation_id,
        "participants": current_user
    })
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
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
        
        # Reset unread count
        await db.conversations.update_one(
            {"id": conversation_id},
            {"$set": {f"unread_counts.{current_user}": 0}}
        )
    
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
    """Send text message"""
    from server import db, sio
    
    conversation = await db.conversations.find_one({
        "id": conversation_id,
        "participants": current_user
    })
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    message = Message(
        conversation_id=conversation_id,
        sender_id=current_user,
        message_type=MessageType(message_type),
        content=content,
        reply_to_id=reply_to_id,
        status=MessageStatus.SENT
    )
    
    await db.messages.insert_one(message.model_dump())
    
    # Update conversation
    preview = content[:50] + "..." if len(content) > 50 else content
    
    # Increment unread for other participants
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
    
    # Emit socket event
    await sio.emit('new_message', message.model_dump(), room=conversation_id)
    
    # Send push notifications to offline users
    sender = await db.users.find_one({"id": current_user})
    sender_name = sender['full_name'] if sender else "Someone"
    
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
    """Send media message (image, video, audio, voice note, document)"""
    from server import db, sio
    
    conversation = await db.conversations.find_one({
        "id": conversation_id,
        "participants": current_user
    })
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Upload to Cloudinary
    try:
        content = await file.read()
        
        resource_type = "auto"
        if message_type in ["voice_note", "audio"]:
            resource_type = "video"  # Cloudinary treats audio as video
        
        result = cloudinary.uploader.upload(
            content,
            resource_type=resource_type,
            folder=f"chat/{conversation_id}"
        )
        
        media_url = result['secure_url']
        media_size = result.get('bytes', 0)
        media_duration = result.get('duration', 0)
        thumbnail = result.get('thumbnail_url')
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    message = Message(
        conversation_id=conversation_id,
        sender_id=current_user,
        message_type=MessageType(message_type),
        content=file.filename or "",
        media_url=media_url,
        media_thumbnail=thumbnail,
        media_duration=int(media_duration) if media_duration else None,
        media_size=media_size,
        status=MessageStatus.SENT
    )
    
    await db.messages.insert_one(message.model_dump())
    
    # Update conversation
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
        {
            "$set": {
                "last_message_id": message.id,
                "last_message_at": message.created_at,
                "last_message_preview": preview
            }
        }
    )
    
    await sio.emit('new_message', message.model_dump(), room=conversation_id)
    
    return {"message_id": message.id, "media_url": media_url}

@chat_router.post("/typing")
async def update_typing_status(
    conversation_id: str,
    is_typing: bool,
    current_user: str = Depends(get_current_user_chat)
):
    """Update typing indicator"""
    from server import db, sio
    
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
    
    await sio.emit('typing', {
        "conversation_id": conversation_id,
        "user_id": current_user,
        "is_typing": is_typing
    }, room=conversation_id)
    
    return {"status": "ok"}

@chat_router.post("/read-receipt")
async def send_read_receipt(
    conversation_id: str,
    message_ids: List[str],
    current_user: str = Depends(get_current_user_chat)
):
    """Mark messages as read"""
    from server import db, sio
    
    await db.messages.update_many(
        {"id": {"$in": message_ids}, "conversation_id": conversation_id},
        {
            "$addToSet": {"read_by": current_user},
            "$set": {"status": MessageStatus.READ.value, "read_at": datetime.utcnow()}
        }
    )
    
    # Reset unread count
    await db.conversations.update_one(
        {"id": conversation_id},
        {"$set": {f"unread_counts.{current_user}": 0}}
    )
    
    await sio.emit('read_receipt', {
        "conversation_id": conversation_id,
        "user_id": current_user,
        "message_ids": message_ids
    }, room=conversation_id)
    
    return {"status": "ok"}

@chat_router.post("/presence")
async def update_presence(
    is_online: bool,
    device_token: Optional[str] = None,
    platform: Optional[str] = None,
    current_user: str = Depends(get_current_user_chat)
):
    """Update user online/offline status"""
    from server import db, sio
    
    await db.user_presence.update_one(
        {"user_id": current_user},
        {
            "$set": {
                "is_online": is_online,
                "last_seen": datetime.utcnow(),
                "device_token": device_token,
                "platform": platform
            }
        },
        upsert=True
    )
    
    # Notify contacts
    await sio.emit('presence', {
        "user_id": current_user,
        "is_online": is_online,
        "last_seen": datetime.utcnow().isoformat()
    }, broadcast=True)
    
    return {"status": "ok"}

@chat_router.get("/presence/{user_id}")
async def get_presence(
    user_id: str,
    current_user: str = Depends(get_current_user_chat)
):
    """Get user's online status"""
    from server import db
    
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
    """Get push notifications"""
    from server import db
    
    query = {"user_id": current_user}
    total = await db.push_notifications.count_documents(query)
    skip = (page - 1) * limit
    
    notifications = await db.push_notifications.find(query).sort(
        "created_at", -1
    ).skip(skip).limit(limit).to_list(length=limit)
    
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
    """Delete message"""
    from server import db, sio
    
    message = await db.messages.find_one({"id": message_id})
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if for_everyone and message['sender_id'] == current_user:
        # Delete for everyone (within 1 hour)
        if datetime.utcnow() - message['created_at'] > timedelta(hours=1):
            raise HTTPException(status_code=400, detail="Can only delete for everyone within 1 hour")
        
        await db.messages.update_one(
            {"id": message_id},
            {"$set": {"is_deleted": True, "content": "This message was deleted"}}
        )
        
        await sio.emit('message_deleted', {
            "message_id": message_id,
            "conversation_id": message['conversation_id'],
            "for_everyone": True
        }, room=message['conversation_id'])
    else:
        # Delete for me only
        await db.messages.update_one(
            {"id": message_id},
            {"$addToSet": {"deleted_for": current_user}}
        )
    
    return {"status": "deleted"}
