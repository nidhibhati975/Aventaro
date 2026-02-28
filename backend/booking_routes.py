"""
AVENTARO BOOKING ROUTES - MODULAR EXTENSION
============================================
Backend APIs for Super Booking Hub
DOES NOT modify existing routes in server.py

Routes Added:
- /api/booking/* (all new booking endpoints)
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List, Optional
from datetime import datetime, timedelta
import uuid
from booking_module import *
import os
import hmac
import hashlib

# Create separate router for booking module
booking_router = APIRouter(prefix="/booking", tags=["booking"])

# Reuse existing auth helper (import from main server)
async def get_current_user_booking(authorization: str = Header(None)) -> str:
    """Reuse existing JWT validation without modifying server.py"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    from server import verify_jwt_token
    user_id = verify_jwt_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id

# =====================
# BOOKING SEARCH ENDPOINTS
# =====================

@booking_router.post("/search", response_model=BookingSearchResponse)
async def search_bookings(
    search_params: BookingSearch,
    current_user: str = Depends(get_current_user_booking)
):
    """
    Universal search endpoint for all booking types
    Returns available hotels, flights, villas, cabs, buses, trains, activities, etc.
    
    NOTE: In production, this will integrate with external APIs:
    - Hotels: Booking.com, Expedia, Agoda APIs
    - Flights: Amadeus, Skyscanner, Kiwi.com APIs
    - Villas: Airbnb, Vrbo APIs
    - Cabs: Uber, Ola APIs
    - Buses: RedBus, FlixBus APIs
    - Trains: IRCTC, Rail Europe APIs
    
    For now, returns mock data structure.
    """
    from server import db
    
    try:
        # Query booking_items collection
        query = {
            "service_type": search_params.service_type,
            "is_available": True
        }
        
        if search_params.destination:
            query["$or"] = [
                {"destination": {"$regex": search_params.destination, "$options": "i"}},
                {"location": {"$regex": search_params.destination, "$options": "i"}}
            ]
        
        if search_params.origin:
            query["origin"] = {"$regex": search_params.origin, "$options": "i"}
        
        if search_params.max_price:
            query["price"] = {"$lte": search_params.max_price}
        
        if search_params.rating_min:
            query["rating"] = {"$gte": search_params.rating_min}
        
        # Get total count
        total = await db.booking_items.count_documents(query)
        
        # Get paginated results
        skip = (search_params.page - 1) * search_params.limit
        cursor = db.booking_items.find(query).skip(skip).limit(search_params.limit)
        items = await cursor.to_list(length=search_params.limit)
        
        results = [BookingItem(**item) for item in items]
        
        return BookingSearchResponse(
            results=results,
            total=total,
            page=search_params.page,
            limit=search_params.limit,
            has_more=(skip + len(results)) < total
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@booking_router.get("/search/{service_type}", response_model=BookingSearchResponse)
async def get_service_listings(
    service_type: str,
    destination: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    current_user: str = Depends(get_current_user_booking)
):
    """Get listings for a specific service type"""
    from server import db
    
    query = {"service_type": service_type, "is_available": True}
    
    if destination:
        query["$or"] = [
            {"destination": {"$regex": destination, "$options": "i"}},
            {"location": {"$regex": destination, "$options": "i"}}
        ]
    
    total = await db.booking_items.count_documents(query)
    skip = (page - 1) * limit
    
    cursor = db.booking_items.find(query).sort("rating", -1).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    
    results = [BookingItem(**item) for item in items]
    
    return BookingSearchResponse(
        results=results,
        total=total,
        page=page,
        limit=limit,
        has_more=(skip + len(results)) < total
    )

@booking_router.get("/item/{item_id}")
async def get_booking_item(
    item_id: str,
    current_user: str = Depends(get_current_user_booking)
):
    """Get detailed information about a booking item"""
    from server import db
    
    item = await db.booking_items.find_one({"id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="Booking item not found")
    
    return item

# =====================
# BOOKING CREATION ENDPOINTS
# =====================

@booking_router.post("/create", response_model=BookingResponse)
async def create_booking(
    booking_request: BookingCreateRequest,
    current_user: str = Depends(get_current_user_booking)
):
    """
    Create a new booking
    Links to existing user system
    Can attach to existing trips
    Tracks referral codes
    """
    from server import db
    
    try:
        # Get booking item
        item = await db.booking_items.find_one({"id": booking_request.booking_item_id})
        if not item:
            raise HTTPException(status_code=404, detail="Booking item not found")
        
        booking_item = BookingItem(**item)
        
        # Calculate amounts
        amount = booking_item.price
        commission_amount = amount * (booking_item.commission_rate / 100)
        
        # Handle referral code
        referrer_user_id = None
        affiliate_commission = 0.0
        
        if booking_request.referral_code:
            referrer = await db.users.find_one({"referral_code": booking_request.referral_code})
            if referrer and referrer['id'] != current_user:
                referrer_user_id = referrer['id']
                # 5% affiliate commission
                affiliate_commission = amount * 0.05
        
        # Validate trip attachment (if provided)
        if booking_request.attach_to_trip_id:
            trip = await db.trips.find_one({"id": booking_request.attach_to_trip_id})
            if not trip:
                raise HTTPException(status_code=404, detail="Trip not found")
            
            # Check if user is trip member
            if current_user not in trip.get('members', []) and current_user != trip.get('creator_id'):
                raise HTTPException(status_code=403, detail="Not authorized to attach to this trip")
        
        # Create booking
        booking = Booking(
            user_id=current_user,
            booking_item_id=booking_request.booking_item_id,
            service_type=booking_request.service_type,
            booking_status="pending",
            payment_status="pending",
            amount=amount,
            currency=booking_item.currency,
            commission_amount=commission_amount,
            guest_name=booking_request.guest_name,
            guest_email=booking_request.guest_email,
            guest_phone=booking_request.guest_phone,
            guest_count=booking_request.guest_count,
            check_in_date=booking_request.check_in_date,
            check_out_date=booking_request.check_out_date,
            departure_date=booking_request.departure_date,
            return_date=booking_request.return_date,
            special_requests=booking_request.special_requests,
            referred_by_code=booking_request.referral_code,
            referrer_user_id=referrer_user_id,
            affiliate_commission=affiliate_commission,
            attached_trip_id=booking_request.attach_to_trip_id
        )
        
        await db.bookings.insert_one(booking.dict())
        
        return BookingResponse(
            booking=booking,
            booking_item=booking_item,
            payment_required=True,
            payment_amount=amount
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Booking creation failed: {str(e)}")

@booking_router.get("/my-bookings")
async def get_my_bookings(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    current_user: str = Depends(get_current_user_booking)
):
    """Get all bookings for current user"""
    from server import db
    
    query = {"user_id": current_user}
    if status:
        query["booking_status"] = status
    
    total = await db.bookings.count_documents(query)
    skip = (page - 1) * limit
    
    cursor = db.bookings.find(query).sort("created_at", -1).skip(skip).limit(limit)
    bookings = await cursor.to_list(length=limit)
    
    # Populate booking items
    for booking in bookings:
        item = await db.booking_items.find_one({"id": booking['booking_item_id']})
        if item:
            booking['booking_item'] = item
    
    return {
        "bookings": bookings,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": (skip + len(bookings)) < total
    }

@booking_router.get("/booking/{booking_id}")
async def get_booking_details(
    booking_id: str,
    current_user: str = Depends(get_current_user_booking)
):
    """Get detailed booking information"""
    from server import db
    
    booking = await db.bookings.find_one({"id": booking_id, "user_id": current_user})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Get booking item
    item = await db.booking_items.find_one({"id": booking['booking_item_id']})
    if item:
        booking['booking_item'] = item
    
    # Get payment if exists
    if booking.get('payment_id'):
        payment = await db.payments.find_one({"id": booking['payment_id']})
        if payment:
            booking['payment'] = payment
    
    return booking

# =====================
# PAYMENT ENDPOINTS
# =====================

@booking_router.post("/payment/create", response_model=PaymentOrderResponse)
async def create_payment_order(
    payment_request: PaymentCreateRequest,
    current_user: str = Depends(get_current_user_booking)
):
    """
    Create payment order
    Supports: Razorpay, Stripe, PayPal, UPI, Cards, Wallets
    """
    from server import db, razorpay_client
    import stripe
    
    try:
        # Get booking
        booking = await db.bookings.find_one({"id": payment_request.booking_id, "user_id": current_user})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        if booking['payment_status'] == "paid":
            raise HTTPException(status_code=400, detail="Booking already paid")
        
        amount_in_paise = int(payment_request.amount * 100)
        
        # Create payment order based on method
        if payment_request.payment_method in ["card", "upi", "wallet"]:
            # Use Razorpay
            order = razorpay_client.order.create({
                'amount': amount_in_paise,
                'currency': payment_request.currency,
                'payment_capture': 1,
                'notes': {
                    'booking_id': payment_request.booking_id,
                    'user_id': current_user
                }
            })
            
            # Create payment record
            payment = Payment(
                user_id=current_user,
                booking_id=payment_request.booking_id,
                payment_method=payment_request.payment_method,
                payment_provider="razorpay",
                amount=payment_request.amount,
                currency=payment_request.currency,
                provider_order_id=order['id']
            )
            
            await db.payments.insert_one(payment.dict())
            
            # Update booking
            await db.bookings.update_one(
                {"id": payment_request.booking_id},
                {"$set": {"payment_id": payment.id, "updated_at": datetime.utcnow()}}
            )
            
            return PaymentOrderResponse(
                order_id=order['id'],
                amount=payment_request.amount,
                currency=payment_request.currency,
                payment_methods=["card", "upi", "wallet", "netbanking"]
            )
        
        else:
            raise HTTPException(status_code=400, detail="Payment method not supported")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment order creation failed: {str(e)}")

@booking_router.post("/payment/verify")
async def verify_payment(
    verify_request: PaymentVerifyRequest,
    current_user: str = Depends(get_current_user_booking)
):
    """
    Verify payment signature (Razorpay/Stripe)
    CRITICAL: Server-side verification only
    """
    from server import db, razorpay_client
    
    try:
        # Get payment
        payment = await db.payments.find_one({"id": verify_request.payment_id, "user_id": current_user})
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        # Verify signature
        if payment['payment_provider'] == "razorpay":
            razorpay_client.utility.verify_payment_signature({
                'razorpay_payment_id': verify_request.provider_payment_id,
                'razorpay_order_id': verify_request.provider_order_id,
                'razorpay_signature': verify_request.provider_signature
            })
        
        # Update payment status
        await db.payments.update_one(
            {"id": verify_request.payment_id},
            {"$set": {
                "status": "completed",
                "provider_payment_id": verify_request.provider_payment_id,
                "provider_signature": verify_request.provider_signature,
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Update booking status
        booking_id = payment['booking_id']
        await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {
                "booking_status": "confirmed",
                "payment_status": "paid",
                "confirmed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Track affiliate commission if referral exists
        booking = await db.bookings.find_one({"id": booking_id})
        if booking and booking.get('referrer_user_id'):
            referral_record = BookingReferral(
                referrer_user_id=booking['referrer_user_id'],
                referee_user_id=current_user,
                booking_id=booking_id,
                referral_code=booking['referred_by_code'],
                commission_amount=booking['affiliate_commission'],
                commission_rate=5.0,  # 5%
                commission_status="pending"
            )
            await db.booking_referrals.insert_one(referral_record.dict())
        
        return {"message": "Payment verified successfully", "booking_status": "confirmed"}
    
    except Exception as e:
        # Update payment as failed
        await db.payments.update_one(
            {"id": verify_request.payment_id},
            {"$set": {"status": "failed", "updated_at": datetime.utcnow()}}
        )
        raise HTTPException(status_code=400, detail=f"Payment verification failed: {str(e)}")

@booking_router.post("/payment/webhook/{provider}")
async def payment_webhook(provider: str, request: dict):
    """
    Webhook handler for payment providers
    Handles: payment.success, payment.failed, refund.processed
    CRITICAL: Signature verification required
    """
    from server import db
    import os
    
    try:
        if provider == "razorpay":
            # Verify webhook signature
            webhook_secret = os.getenv('RAZORPAY_WEBHOOK_SECRET', '')
            signature = request.get('signature', '')
            
            # Verify signature
            generated_signature = hmac.new(
                webhook_secret.encode(),
                str(request.get('payload', '')).encode(),
                hashlib.sha256
            ).hexdigest()
            
            if signature != generated_signature:
                raise HTTPException(status_code=401, detail="Invalid signature")
            
            # Process webhook event
            event_type = request.get('event')
            payload = request.get('payload')
            
            if event_type == "payment.captured":
                # Payment successful
                payment_id = payload['payment']['entity']['id']
                order_id = payload['payment']['entity']['order_id']
                
                # Update payment
                await db.payments.update_one(
                    {"provider_order_id": order_id},
                    {"$set": {
                        "status": "completed",
                        "provider_payment_id": payment_id,
                        "completed_at": datetime.utcnow()
                    }}
                )
                
                # Update booking
                payment = await db.payments.find_one({"provider_order_id": order_id})
                if payment:
                    await db.bookings.update_one(
                        {"id": payment['booking_id']},
                        {"$set": {
                            "booking_status": "confirmed",
                            "payment_status": "paid",
                            "confirmed_at": datetime.utcnow()
                        }}
                    )
            
            elif event_type == "payment.failed":
                # Payment failed
                order_id = payload['payment']['entity']['order_id']
                await db.payments.update_one(
                    {"provider_order_id": order_id},
                    {"$set": {"status": "failed", "updated_at": datetime.utcnow()}}
                )
        
        return {"status": "ok"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

# =====================
# REFUND ENDPOINTS
# =====================

@booking_router.post("/refund/request")
async def request_refund(
    refund_request: RefundCreateRequest,
    current_user: str = Depends(get_current_user_booking)
):
    """Request refund for a booking"""
    from server import db
    
    try:
        # Get booking
        booking = await db.bookings.find_one({"id": refund_request.booking_id, "user_id": current_user})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        if booking['payment_status'] != "paid":
            raise HTTPException(status_code=400, detail="Booking not paid yet")
        
        # Get payment
        payment = await db.payments.find_one({"id": booking['payment_id']})
        if not payment:
            raise HTTPException(status_code=404, detail="Payment record not found")
        
        # Calculate refund amount (full or partial)
        refund_amount = refund_request.refund_amount if refund_request.refund_amount else booking['amount']
        
        # Create refund request
        refund = RefundRequest(
            booking_id=refund_request.booking_id,
            user_id=current_user,
            payment_id=payment['id'],
            refund_amount=refund_amount,
            refund_reason=refund_request.refund_reason
        )
        
        await db.refund_requests.insert_one(refund.dict())
        
        # Update booking
        await db.bookings.update_one(
            {"id": refund_request.booking_id},
            {"$set": {
                "cancellation_requested_at": datetime.utcnow(),
                "cancellation_reason": refund_request.refund_reason,
                "refund_status": "pending",
                "updated_at": datetime.utcnow()
            }}
        )
        
        return {"message": "Refund request submitted", "refund_id": refund.id}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refund request failed: {str(e)}")

# =====================
# REVIEW ENDPOINTS
# =====================

@booking_router.post("/review/create")
async def create_review(
    review_request: ReviewCreateRequest,
    current_user: str = Depends(get_current_user_booking)
):
    """Create review for a completed booking"""
    from server import db
    
    try:
        # Verify booking exists and belongs to user
        booking = await db.bookings.find_one({"id": review_request.booking_id, "user_id": current_user})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        if booking['booking_status'] != "completed":
            raise HTTPException(status_code=400, detail="Can only review completed bookings")
        
        # Get booking item details
        item = await db.booking_items.find_one({"id": booking['booking_item_id']})
        if not item:
            raise HTTPException(status_code=404, detail="Booking item not found")
        
        # Create review
        review = BookingReview(
            booking_id=review_request.booking_id,
            user_id=current_user,
            service_type=booking['service_type'],
            provider_name=item['provider_name'],
            rating=review_request.rating,
            title=review_request.title,
            review_text=review_request.review_text,
            images=review_request.images,
            is_verified_booking=True
        )
        
        await db.booking_reviews.insert_one(review.dict())
        
        # Update booking item average rating
        reviews = await db.booking_reviews.find({"service_type": booking['service_type'], "provider_name": item['provider_name']}).to_list(length=1000)
        avg_rating = sum(r['rating'] for r in reviews) / len(reviews) if reviews else 0
        reviews_count = len(reviews)
        
        await db.booking_items.update_one(
            {"id": item['id']},
            {"$set": {
                "rating": round(avg_rating, 1),
                "reviews_count": reviews_count,
                "updated_at": datetime.utcnow()
            }}
        )
        
        return {"message": "Review created successfully", "review_id": review.id}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Review creation failed: {str(e)}")

@booking_router.get("/reviews/{service_type}")
async def get_reviews(
    service_type: str,
    provider_name: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    current_user: str = Depends(get_current_user_booking)
):
    """Get reviews for a service type or provider"""
    from server import db
    
    query = {"service_type": service_type}
    if provider_name:
        query["provider_name"] = provider_name
    
    total = await db.booking_reviews.count_documents(query)
    skip = (page - 1) * limit
    
    cursor = db.booking_reviews.find(query).sort("created_at", -1).skip(skip).limit(limit)
    reviews = await cursor.to_list(length=limit)
    
    return {
        "reviews": reviews,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": (skip + len(reviews)) < total
    }

# =====================
# AFFILIATE/REFERRAL ENDPOINTS
# =====================

@booking_router.get("/referrals/my-earnings")
async def get_my_affiliate_earnings(
    current_user: str = Depends(get_current_user_booking)
):
    """Get affiliate earnings for current user"""
    from server import db
    
    # Get all referrals
    referrals = await db.booking_referrals.find({"referrer_user_id": current_user}).to_list(length=1000)
    
    total_earnings = sum(r['commission_amount'] for r in referrals)
    pending_earnings = sum(r['commission_amount'] for r in referrals if r['commission_status'] == 'pending')
    approved_earnings = sum(r['commission_amount'] for r in referrals if r['commission_status'] == 'approved')
    paid_earnings = sum(r['commission_amount'] for r in referrals if r['commission_status'] == 'paid')
    
    return {
        "total_earnings": total_earnings,
        "pending_earnings": pending_earnings,
        "approved_earnings": approved_earnings,
        "paid_earnings": paid_earnings,
        "total_referrals": len(referrals),
        "referrals": referrals
    }

@booking_router.get("/referrals/stats")
async def get_referral_stats(
    current_user: str = Depends(get_current_user_booking)
):
    """Get referral statistics"""
    from server import db
    
    # Get user's referral code
    user = await db.users.find_one({"id": current_user})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    referral_code = user.get('referral_code')
    
    # Count bookings using this referral code
    referral_count = await db.bookings.count_documents({"referred_by_code": referral_code})
    
    # Get total commission earned
    referrals = await db.booking_referrals.find({"referrer_user_id": current_user}).to_list(length=1000)
    total_commission = sum(r['commission_amount'] for r in referrals)
    
    return {
        "referral_code": referral_code,
        "total_referrals": referral_count,
        "total_commission": total_commission,
        "recent_referrals": referrals[:5]  # Last 5
    }
