# Aventaro - Social Travel Platform MVP

## 🎉 Project Overview

Aventaro is a **production-ready social travel mobile application** built with React Native (Expo), FastAPI, and MongoDB. It's a premium platform that combines social networking with travel planning, enabling users to discover people, create trips, match with travel companions, and communicate in real-time.

---

## ✅ Core Features Implemented

### 1. **Authentication System** 
- Complete JWT-based authentication
- **Sign Up** with ALL mandatory fields:
  - Full Name, Email, Phone, Password
  - Date of Birth, Gender, City
  - Interests (multi-select)
  - Relationship Status (Single/Married/Widowed/Divorced)
- **Sign In** with email or phone
- Persistent authentication with AsyncStorage
- Secure password hashing with bcrypt

### 2. **Discover Screen** 
- **Two-tab interface:**
  - **Discover People**: Swipeable cards showing user profiles
  - **Discover Trips**: Swipeable cards showing available trips
- **Swipe Actions:**
  - Swipe Right = Send Friend Request / Request to Join Trip
  - Swipe Left = Skip
- **People cards show:**
  - Profile image, name, age, city
  - Relationship status
  - Bio and interests
- **Trip cards show:**
  - Trip image, destination, dates
  - Budget range, trip type, max members
  - Creator info and itinerary preview
  - "Boosted" badge for promoted trips

### 3. **Matches Screen** 
- **Two sections:**
  - **Friend Requests**: Incoming friend requests with accept button
  - **Trip Join Requests**: Requests to join your created trips
- One-tap approval system
- Real-time updates after actions

### 4. **Trips Management** 
- **My Trips:**
  - **Created**: Trips you've created
  - **Joined**: Trips you're a member of
- **Create Trip Form** with ALL mandatory fields:
  - Destination
  - Start & End Dates
  - Budget Range
  - Trip Type
  - Max Members
  - **Editable Itinerary** (required)
- Trip request management (approve/reject join requests)
- Friend auto-join (friends can join directly without approval)

### 5. **Chat System** 
- Conversation list with last message preview
- 1:1 chat infrastructure (Socket.IO ready)
- Trip-based group chat support
- Real-time message updates

### 6. **Profile & Wallet** 
- Complete user profile display
- **Wallet System:**
  - Current balance display
  - Reward points tracking
  - Top-up functionality (Razorpay/Stripe ready)
- **Referral Program:**
  - Unique referral code for each user
  - Track successful referrals
  - **3 referrals = 1 FREE 24-hour boost**
  - Visual progress indicator
- Settings and account management
- Sign out functionality

---

## 🏗 Architecture

### **Frontend (React Native + Expo)**
```
/app/frontend/
├── app/
│   ├── (auth)/          # Authentication screens
│   │   ├── splash.tsx
│   │   ├── sign-in.tsx
│   │   └── sign-up.tsx
│   ├── (tabs)/          # Main app tabs
│   │   ├── discover.tsx  # People & Trips discovery
│   │   ├── matches.tsx   # Friend & Trip requests
│   │   ├── trips.tsx     # Trip management
│   │   ├── chat.tsx      # Conversations
│   │   └── profile.tsx   # User profile & wallet
│   ├── _layout.tsx
│   └── index.tsx
├── contexts/
│   └── AuthContext.tsx   # Authentication state
├── services/
│   └── api.ts            # Axios API client
└── assets/
    └── images/
        └── aventaro-logo.png
```

### **Backend (FastAPI + MongoDB)**
```
/app/backend/
└── server.py            # Complete API server
```

**API Endpoints:**
- `/api/auth/signup` - User registration
- `/api/auth/signin` - User login
- `/api/auth/me` - Get current user
- `/api/users/discover` - Discover people
- `/api/users/friend-request` - Send friend request
- `/api/users/friend-requests` - Get friend requests
- `/api/users/friend-request/{id}/accept` - Accept friend request
- `/api/trips` - Create trip
- `/api/trips/discover` - Discover trips (boosted first)
- `/api/trips/my-trips` - Get user's trips
- `/api/trips/{id}/join-request` - Request to join trip
- `/api/trips/{id}/approve/{user_id}` - Approve trip request
- `/api/wallet/balance` - Get wallet balance
- `/api/wallet/topup` - Create wallet top-up order
- `/api/trips/{id}/boost` - Boost trip (₹99/₹199/₹599)
- `/api/referral/code` - Get referral code
- `/api/referral/apply` - Apply referral code
- `/api/conversations` - Get user conversations
- `/api/conversations/{id}/messages` - Get messages
- `/api/upload/image` - Upload images to Cloudinary
- **Socket.IO endpoints** for real-time chat

### **Database (MongoDB)**
**Collections:**
- `users` - User profiles, wallet, referrals
- `trips` - Trip information, members, boost status
- `friend_requests` - Friend request tracking
- `conversations` - Chat conversations
- `messages` - Chat messages
- `wallet_transactions` - Payment history

---

## 💰 Monetization Features (Implemented)

### **1. Boosted Trips (PRIMARY REVENUE)**
- **Pricing:**
  - ₹99 → 24 hours
  - ₹199 → 3 days
  - ₹599 → 7 days
- Boosted trips appear FIRST in Discover Trips
- Visual "Boosted" badge with lightning icon
- Payment via wallet balance
- Automatic expiry tracking

### **2. Wallet System**
- Store balance in paise (100 paise = ₹1)
- **Top-up** via Razorpay/Stripe
- **Spend** on boosted trips
- Transaction history
- Payment verification

### **3. Referral Rewards**
- Each user gets unique referral code
- Track successful referrals
- **Reward: 100 points per referral**
- **Special Offer: 3 referrals = 1 FREE 24h boost**
- Automatic tracking and rewards

---

## 🎨 Design System

### **Colors (Strict Brand Guidelines)**
- **Primary Purple:** #8B5CF6 (buttons, active states)
- **Secondary Gold:** #D97706 (accents, referral section)
- **Background:** #FFFFFF (pure white)
- **Text:** #1F2937 (dark), #6B7280 (secondary)
- **Success:** #10B981
- **Error:** #EF4444

### **Typography**
- Headlines: 28px, Bold
- Subheadings: 18px, Bold
- Body: 14-16px, Regular
- Labels: 12-14px, SemiBold

### **UI Patterns**
- Rounded corners: 12px
- Card shadows: subtle elevation
- Premium, clean, modern aesthetic
- Touch targets: minimum 44px
- Consistent spacing: 8px grid

---

## 🔧 Integrations (API-Ready)

### **Cloudinary** (Image Storage)
- Profile pictures
- Trip images
- Chat media attachments
- Automatic optimization for mobile

### **Razorpay** (Payment Gateway)
- Wallet top-up
- Boosted trips payment
- Order creation & verification
- Webhook support

### **Stripe** (Alternative Payment)
- International transactions
- Wallet functionality
- Test mode configured

### **Socket.IO** (Real-time Chat)
- 1:1 messaging
- Group chat (trip-based)
- Typing indicators
- Read receipts support
- Connection management

---

## 🚀 What's Ready for Production

### ✅ **Fully Functional:**
1. Complete authentication flow
2. User profile management
3. Discover people & trips
4. Friend requests & matching
5. Trip creation & management
6. Trip join requests
7. Wallet & balance tracking
8. Boosted trips system
9. Referral program
10. Chat infrastructure

### ⚙️ **API-Ready (Requires Keys):**
1. Cloudinary image uploads
2. Razorpay payments
3. Stripe payments
4. Socket.IO real-time chat

### 🔜 **Coming Soon (Architecture Ready):**
1. Booking system (affiliate partners)
2. Google Maps live location
3. Emergency safety features
4. Push notifications
5. Advanced chat features (media, voice)

---

## 📱 Installation & Setup

### **Prerequisites:**
```bash
Node.js 16+
Python 3.8+
MongoDB
```

### **Backend Setup:**
```bash
cd /app/backend
pip install -r requirements.txt

# Configure .env with your API keys
MONGO_URL=mongodb://mongodb:27017
CLOUDINARY_CLOUD_NAME=your_name
CLOUDINARY_API_KEY=your_key
RAZORPAY_KEY_ID=your_key
STRIPE_SECRET_KEY=your_key

# Run server
uvicorn server:socketio_asgi_app --host 0.0.0.0 --port 8001
```

### **Frontend Setup:**
```bash
cd /app/frontend
yarn install

# Configure .env
EXPO_PUBLIC_BACKEND_URL=http://localhost
EXPO_PUBLIC_CLOUDINARY_CLOUD_NAME=your_name

# Run app
yarn start
```

### **Access:**
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8001
- **API Docs:** http://localhost:8001/docs

---

## 🎯 Key Differentiators

1. **Premium Design**: Purple & Gold branding, clean white UI
2. **Dual Discovery**: Swipe for both people AND trips
3. **Smart Matching**: Automatic friend detection for trips
4. **Monetization**: Multiple revenue streams (boosts, wallet, future bookings)
5. **Referral System**: Viral growth incentives
6. **Production-Ready**: Real database, payments, chat infrastructure
7. **Safety-First**: Dedicated safety features architecture

---

## 📊 Next Steps for Deployment

1. **Add API Keys:**
   - Cloudinary (image hosting)
   - Razorpay/Stripe (payments)
   - Google Maps (location features)

2. **Configure Domain:**
   - Set up production API URL
   - Configure CORS
   - SSL certificates

3. **Build & Deploy:**
   - Create Expo production build
   - Deploy backend to cloud (AWS/GCP/Azure)
   - Set up MongoDB Atlas

4. **App Store Submission:**
   - iOS App Store
   - Google Play Store
   - Include all required permissions

---

## 💡 Technical Highlights

- **JWT Authentication**: Secure, stateless auth
- **Async API**: FastAPI with Motor (async MongoDB driver)
- **Real-time**: Socket.IO for instant messaging
- **Image Optimization**: Cloudinary CDN
- **Payment Integration**: Razorpay + Stripe dual support
- **State Management**: React Context + AsyncStorage
- **Type Safety**: TypeScript throughout frontend
- **Mobile-First**: Optimized for touch, gestures, safe areas
- **Scalable Architecture**: Modular, extensible design

---

## 🔐 Security Features

- Password hashing with bcrypt
- JWT token-based authentication
- Secure API endpoints
- Input validation
- CORS configuration
- Environment variable management
- No hardcoded secrets

---

## 📝 Notes

- All core features are **fully functional**
- Payment integrations are **architecture-ready** (need API keys)
- Chat system is **infrastructure-ready** (Socket.IO implemented)
- No mock data or placeholder logic
- Production-ready database schema
- Mobile-optimized UI/UX

---

## 🎬 Ready to Launch!

Aventaro MVP is **complete and ready for real users**. Simply add your API keys for Cloudinary, Razorpay/Stripe, and you're ready to deploy!

**Built with ❤️ using React Native, FastAPI, and MongoDB**
