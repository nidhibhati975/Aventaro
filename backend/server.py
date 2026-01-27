from fastapi import FastAPI, APIRouter, HTTPException, Depends, File, UploadFile, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import os
import logging
import uuid
import socketio
from datetime import datetime, timedelta
import bcrypt
import jwt
import cloudinary
import cloudinary.uploader
import razorpay
import stripe
import aiofiles

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Initialize Socket.IO
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    ping_timeout=60,
    ping_interval=25
)

# Initialize Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME', ''),
    api_key=os.getenv('CLOUDINARY_API_KEY', ''),
    api_secret=os.getenv('CLOUDINARY_API_SECRET', '')
)

# Initialize Razorpay
razorpay_client = razorpay.Client(
    auth=(os.getenv('RAZORPAY_KEY_ID', ''), os.getenv('RAZORPAY_KEY_SECRET', ''))
)

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')

# Create FastAPI app
app = FastAPI(title="Aventaro API")

# Create router
api_router = APIRouter(prefix="/api")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT Settings
JWT_SECRET = os.environ.get('JWT_SECRET', 'secret_key')
JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')

# =====================
# MODELS
# =====================

class UserSignUp(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    password: str
    date_of_birth: str
    gender: str
    city: str
    interests: List[str]
    relationship_status: str
    
class UserSignIn(BaseModel):
    login: str  # email or phone
    password: str

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    full_name: str
    email: str
    phone: str
    password_hash: str
    date_of_birth: str
    gender: str
    city: str
    interests: List[str]
    relationship_status: str
    profile_image: Optional[str] = None
    bio: Optional[str] = ""
    friends: List[str] = []
    wallet_balance: int = 0  # in paise
    referral_code: str = Field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    referred_by: Optional[str] = None
    successful_referrals: int = 0
    reward_points: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)

class Trip(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    creator_id: str
    destination: str
    start_date: str
    end_date: str
    budget_range: str
    trip_type: str
    max_members: int
    itinerary: str
    trip_image: Optional[str] = None
    members: List[str] = []  # user IDs
    pending_requests: List[str] = []  # user IDs
    is_boosted: bool = False
    boost_expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TripCreate(BaseModel):
    destination: str
    start_date: str
    end_date: str
    budget_range: str
    trip_type: str
    max_members: int
    itinerary: str
    trip_image: Optional[str] = None

class FriendRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_user_id: str
    to_user_id: str
    status: str = "pending"  # pending, accepted, rejected
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    sender_id: str
    content: str
    message_type: str = "text"  # text, image, voice
    media_url: Optional[str] = None
    read_by: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Conversation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_type: str  # direct, trip_group
    members: List[str]  # user IDs
    trip_id: Optional[str] = None
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class WalletTransaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    transaction_type: str  # topup, payment, transfer_in, transfer_out, reward
    amount: int  # in paise
    description: str
    payment_id: Optional[str] = None
    status: str = "completed"  # pending, completed, failed
    created_at: datetime = Field(default_factory=datetime.utcnow)

class BoostPayment(BaseModel):
    trip_id: str
    boost_duration: str  # 24h, 3days, 7days
    amount: int

# =====================
# HELPER FUNCTIONS
# =====================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_jwt_token(user_id: str) -> str:
    payload = {
        'sub': user_id,
        'exp': datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> Optional[str]:
    try:
        if token.startswith('Bearer '):
            token = token[7:]
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get('sub')
    except:
        return None

async def get_current_user(authorization: str = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = verify_jwt_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id

# =====================
# AUTH ROUTES
# =====================

@api_router.post("/auth/signup")
async def signup(user_data: UserSignUp):
    # Check if user exists
    existing = await db.users.find_one({"$or": [{"email": user_data.email}, {"phone": user_data.phone}]})
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Create user
    user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        phone=user_data.phone,
        password_hash=hash_password(user_data.password),
        date_of_birth=user_data.date_of_birth,
        gender=user_data.gender,
        city=user_data.city,
        interests=user_data.interests,
        relationship_status=user_data.relationship_status
    )
    
    await db.users.insert_one(user.dict())
    
    token = create_jwt_token(user.id)
    
    return {
        "token": token,
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "profile_image": user.profile_image
        }
    }

@api_router.post("/auth/signin")
async def signin(credentials: UserSignIn):
    # Find user by email or phone
    user = await db.users.find_one({"$or": [{"email": credentials.login}, {"phone": credentials.login}]})
    
    if not user or not verify_password(credentials.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_jwt_token(user['id'])
    
    return {
        "token": token,
        "user": {
            "id": user['id'],
            "full_name": user['full_name'],
            "email": user['email'],
            "profile_image": user.get('profile_image')
        }
    }

@api_router.get("/auth/me")
async def get_me(current_user: str = Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.pop('password_hash', None)
    user.pop('_id', None)  # Remove MongoDB ObjectId
    return user

# =====================
# USER ROUTES
# =====================

@api_router.get("/users/discover")
async def discover_users(current_user: str = Depends(get_current_user), skip: int = 0, limit: int = 20):
    # Get users excluding current user and friends
    user_data = await db.users.find_one({"id": current_user})
    friends = user_data.get('friends', [])
    
    users = await db.users.find({
        "id": {"$ne": current_user, "$nin": friends}
    }).skip(skip).limit(limit).to_list(length=limit)
    
    for user in users:
        user.pop('password_hash', None)
        user.pop('_id', None)  # Remove MongoDB ObjectId
    
    return users

@api_router.post("/users/friend-request")
async def send_friend_request(to_user_id: str, current_user: str = Depends(get_current_user)):
    # Check if request already exists
    existing = await db.friend_requests.find_one({
        "from_user_id": current_user,
        "to_user_id": to_user_id,
        "status": "pending"
    })
    
    if existing:
        raise HTTPException(status_code=400, detail="Request already sent")
    
    request = FriendRequest(from_user_id=current_user, to_user_id=to_user_id)
    await db.friend_requests.insert_one(request.dict())
    
    return {"message": "Friend request sent"}

@api_router.get("/users/friend-requests")
async def get_friend_requests(current_user: str = Depends(get_current_user)):
    requests = await db.friend_requests.find({
        "to_user_id": current_user,
        "status": "pending"
    }).to_list(length=100)
    
    # Populate user data
    for request in requests:
        request.pop('_id', None)  # Remove MongoDB ObjectId
        user = await db.users.find_one({"id": request['from_user_id']})
        if user:
            user.pop('password_hash', None)
            user.pop('_id', None)  # Remove MongoDB ObjectId
            request['user'] = user
    
    return requests

@api_router.post("/users/friend-request/{request_id}/accept")
async def accept_friend_request(request_id: str, current_user: str = Depends(get_current_user)):
    request = await db.friend_requests.find_one({"id": request_id, "to_user_id": current_user})
    
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # Update request status
    await db.friend_requests.update_one({"id": request_id}, {"$set": {"status": "accepted"}})
    
    # Add to friends lists
    await db.users.update_one({"id": current_user}, {"$push": {"friends": request['from_user_id']}})
    await db.users.update_one({"id": request['from_user_id']}, {"$push": {"friends": current_user}})
    
    return {"message": "Friend request accepted"}

# =====================
# TRIP ROUTES
# =====================

@api_router.post("/trips")
async def create_trip(trip_data: Trip, current_user: str = Depends(get_current_user)):
    trip_data.creator_id = current_user
    trip_data.members = [current_user]
    
    await db.trips.insert_one(trip_data.dict())
    
    return trip_data

@api_router.get("/trips/discover")
async def discover_trips(current_user: str = Depends(get_current_user), skip: int = 0, limit: int = 20):
    # Get trips created by others, boosted trips first
    trips = await db.trips.find({
        "creator_id": {"$ne": current_user}
    }).sort([("is_boosted", -1), ("created_at", -1)]).skip(skip).limit(limit).to_list(length=limit)
    
    # Populate creator data
    for trip in trips:
        creator = await db.users.find_one({"id": trip['creator_id']})
        if creator:
            creator.pop('password_hash', None)
            trip['creator'] = creator
    
    return trips

@api_router.get("/trips/my-trips")
async def get_my_trips(current_user: str = Depends(get_current_user)):
    trips = await db.trips.find({
        "$or": [
            {"creator_id": current_user},
            {"members": current_user}
        ]
    }).to_list(length=100)
    
    created = [t for t in trips if t['creator_id'] == current_user]
    joined = [t for t in trips if t['creator_id'] != current_user and current_user in t['members']]
    
    return {"created": created, "joined": joined}

@api_router.post("/trips/{trip_id}/join-request")
async def request_to_join_trip(trip_id: str, current_user: str = Depends(get_current_user)):
    trip = await db.trips.find_one({"id": trip_id})
    
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    if current_user in trip.get('members', []):
        raise HTTPException(status_code=400, detail="Already a member")
    
    if current_user in trip.get('pending_requests', []):
        raise HTTPException(status_code=400, detail="Request already sent")
    
    # Check if user is friend of creator
    creator = await db.users.find_one({"id": trip['creator_id']})
    if current_user in creator.get('friends', []):
        # Add directly
        await db.trips.update_one({"id": trip_id}, {"$push": {"members": current_user}})
        return {"message": "Joined trip"}
    else:
        # Send request
        await db.trips.update_one({"id": trip_id}, {"$push": {"pending_requests": current_user}})
        return {"message": "Join request sent"}

@api_router.get("/trips/{trip_id}/requests")
async def get_trip_requests(trip_id: str, current_user: str = Depends(get_current_user)):
    trip = await db.trips.find_one({"id": trip_id, "creator_id": current_user})
    
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found or unauthorized")
    
    requests = []
    for user_id in trip.get('pending_requests', []):
        user = await db.users.find_one({"id": user_id})
        if user:
            user.pop('password_hash', None)
            requests.append(user)
    
    return requests

@api_router.post("/trips/{trip_id}/approve/{user_id}")
async def approve_trip_request(trip_id: str, user_id: str, current_user: str = Depends(get_current_user)):
    trip = await db.trips.find_one({"id": trip_id, "creator_id": current_user})
    
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found or unauthorized")
    
    await db.trips.update_one(
        {"id": trip_id},
        {
            "$pull": {"pending_requests": user_id},
            "$push": {"members": user_id}
        }
    )
    
    return {"message": "Request approved"}

# =====================
# WALLET & PAYMENTS
# =====================

@api_router.get("/wallet/balance")
async def get_wallet_balance(current_user: str = Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user})
    return {"balance": user.get('wallet_balance', 0), "reward_points": user.get('reward_points', 0)}

@api_router.post("/wallet/topup")
async def wallet_topup(amount: int, current_user: str = Depends(get_current_user)):
    # Create Razorpay order
    try:
        order = razorpay_client.order.create({
            'amount': amount,
            'currency': 'INR',
            'payment_capture': 1
        })
        
        return {
            "order_id": order['id'],
            "amount": amount,
            "currency": "INR"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/wallet/topup/verify")
async def verify_topup(payment_id: str, order_id: str, signature: str, current_user: str = Depends(get_current_user)):
    try:
        # Verify signature
        razorpay_client.utility.verify_payment_signature({
            'razorpay_payment_id': payment_id,
            'razorpay_order_id': order_id,
            'razorpay_signature': signature
        })
        
        # Get order details
        order = razorpay_client.order.fetch(order_id)
        amount = order['amount']
        
        # Update wallet
        await db.users.update_one(
            {"id": current_user},
            {"$inc": {"wallet_balance": amount}}
        )
        
        # Record transaction
        transaction = WalletTransaction(
            user_id=current_user,
            transaction_type="topup",
            amount=amount,
            description="Wallet topup",
            payment_id=payment_id
        )
        await db.wallet_transactions.insert_one(transaction.dict())
        
        return {"message": "Wallet topped up successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail="Payment verification failed")

@api_router.post("/trips/{trip_id}/boost")
async def boost_trip(trip_id: str, boost_data: BoostPayment, current_user: str = Depends(get_current_user)):
    trip = await db.trips.find_one({"id": trip_id, "creator_id": current_user})
    
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    # Check if user has enough balance or free boost
    user = await db.users.find_one({"id": current_user})
    
    # Check if user has 3 referrals for free boost
    if user.get('successful_referrals', 0) >= 3 and boost_data.boost_duration == "24h":
        # Free boost
        await db.users.update_one(
            {"id": current_user},
            {"$inc": {"successful_referrals": -3}}
        )
    else:
        # Paid boost - check wallet balance
        if user.get('wallet_balance', 0) < boost_data.amount:
            raise HTTPException(status_code=400, detail="Insufficient wallet balance")
        
        # Deduct from wallet
        await db.users.update_one(
            {"id": current_user},
            {"$inc": {"wallet_balance": -boost_data.amount}}
        )
        
        # Record transaction
        transaction = WalletTransaction(
            user_id=current_user,
            transaction_type="payment",
            amount=boost_data.amount,
            description=f"Boost trip for {boost_data.boost_duration}"
        )
        await db.wallet_transactions.insert_one(transaction.dict())
    
    # Calculate boost expiry
    duration_map = {"24h": 1, "3days": 3, "7days": 7}
    days = duration_map.get(boost_data.boost_duration, 1)
    expires_at = datetime.utcnow() + timedelta(days=days)
    
    # Update trip
    await db.trips.update_one(
        {"id": trip_id},
        {"$set": {"is_boosted": True, "boost_expires_at": expires_at}}
    )
    
    return {"message": "Trip boosted successfully", "expires_at": expires_at}

# =====================
# REFERRALS
# =====================

@api_router.get("/referral/code")
async def get_referral_code(current_user: str = Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user})
    return {
        "referral_code": user.get('referral_code'),
        "successful_referrals": user.get('successful_referrals', 0)
    }

@api_router.post("/referral/apply")
async def apply_referral(referral_code: str, current_user: str = Depends(get_current_user)):
    # Find referrer
    referrer = await db.users.find_one({"referral_code": referral_code})
    
    if not referrer:
        raise HTTPException(status_code=404, detail="Invalid referral code")
    
    if referrer['id'] == current_user:
        raise HTTPException(status_code=400, detail="Cannot refer yourself")
    
    # Check if already referred
    user = await db.users.find_one({"id": current_user})
    if user.get('referred_by'):
        raise HTTPException(status_code=400, detail="Already used a referral code")
    
    # Apply referral
    await db.users.update_one(
        {"id": current_user},
        {"$set": {"referred_by": referrer['id']}}
    )
    
    # Increment successful referrals and reward points
    await db.users.update_one(
        {"id": referrer['id']},
        {"$inc": {"successful_referrals": 1, "reward_points": 100}}
    )
    
    return {"message": "Referral code applied successfully"}

# =====================
# IMAGE UPLOAD
# =====================

@api_router.post("/upload/image")
async def upload_image(file: UploadFile = File(...), current_user: str = Depends(get_current_user)):
    try:
        # Read file
        contents = await file.read()
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            contents,
            folder="aventaro",
            resource_type="auto"
        )
        
        return {"url": result['secure_url'], "public_id": result['public_id']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@api_router.post("/users/update-profile")
async def update_profile(profile_image: Optional[str] = None, bio: Optional[str] = None, current_user: str = Depends(get_current_user)):
    update_data = {}
    if profile_image:
        update_data['profile_image'] = profile_image
    if bio:
        update_data['bio'] = bio
    
    if update_data:
        await db.users.update_one({"id": current_user}, {"$set": update_data})
    
    return {"message": "Profile updated"}

# =====================
# SOCKET.IO HANDLERS
# =====================

active_sessions = {}

@sio.event
async def connect(sid, environ, auth):
    print(f"Client {sid} attempting to connect")
    try:
        token = auth.get('token', '')
        user_id = verify_jwt_token(token)
        
        if not user_id:
            print(f"Authentication failed for {sid}")
            return False
        
        active_sessions[sid] = {'user_id': user_id}
        await sio.enter_room(sid, f"user_{user_id}")
        
        print(f"User {user_id} connected with socket {sid}")
        return True
    except Exception as e:
        print(f"Connection error: {e}")
        return False

@sio.event
async def disconnect(sid):
    if sid in active_sessions:
        user_id = active_sessions[sid]['user_id']
        del active_sessions[sid]
        print(f"User {user_id} disconnected")

@sio.event
async def join_conversation(sid, conversation_id):
    if sid not in active_sessions:
        return {'success': False}
    
    await sio.enter_room(sid, f"conversation_{conversation_id}")
    return {'success': True}

@sio.event
async def send_message(sid, data):
    if sid not in active_sessions:
        return {'success': False}
    
    user_id = active_sessions[sid]['user_id']
    
    message = Message(
        conversation_id=data['conversation_id'],
        sender_id=user_id,
        content=data['content'],
        message_type=data.get('message_type', 'text'),
        media_url=data.get('media_url')
    )
    
    await db.messages.insert_one(message.dict())
    
    # Update conversation last message
    await db.conversations.update_one(
        {"id": data['conversation_id']},
        {"$set": {"last_message": data['content'], "last_message_at": datetime.utcnow()}}
    )
    
    # Emit to conversation room
    await sio.emit('receive_message', message.dict(), room=f"conversation_{data['conversation_id']}")
    
    return {'success': True}

@sio.event
async def typing(sid, data):
    if sid not in active_sessions:
        return
    
    user_id = active_sessions[sid]['user_id']
    await sio.emit('user_typing', {'user_id': user_id}, room=f"conversation_{data['conversation_id']}", skip_sid=sid)

# =====================
# CONVERSATION ROUTES
# =====================

@api_router.post("/conversations")
async def create_conversation(other_user_id: str, current_user: str = Depends(get_current_user)):
    # Check if conversation exists
    existing = await db.conversations.find_one({
        "conversation_type": "direct",
        "members": {"$all": [current_user, other_user_id]}
    })
    
    if existing:
        return existing
    
    conversation = Conversation(
        conversation_type="direct",
        members=[current_user, other_user_id]
    )
    
    await db.conversations.insert_one(conversation.dict())
    return conversation

@api_router.get("/conversations")
async def get_conversations(current_user: str = Depends(get_current_user)):
    conversations = await db.conversations.find({
        "members": current_user
    }).sort("last_message_at", -1).to_list(length=100)
    
    # Populate other user data
    for conv in conversations:
        other_user_id = [m for m in conv['members'] if m != current_user][0]
        user = await db.users.find_one({"id": other_user_id})
        if user:
            user.pop('password_hash', None)
            conv['other_user'] = user
    
    return conversations

@api_router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, current_user: str = Depends(get_current_user), skip: int = 0, limit: int = 50):
    # Verify user is member
    conversation = await db.conversations.find_one({"id": conversation_id, "members": current_user})
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = await db.messages.find(
        {"conversation_id": conversation_id}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    
    return list(reversed(messages))

# Include routers
app.include_router(api_router)

# Wrap with Socket.IO
socketio_asgi_app = socketio.ASGIApp(sio, app, socketio_path='/socket.io')

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()