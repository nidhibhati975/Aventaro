"""
AFFILIATE ROUTES - Production Hardened
Security: Self-referral prevention, fraud detection, commission validation
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Response, Request
from typing import Optional
from datetime import datetime, timedelta
import uuid
import hashlib
import logging
from affiliate_module import *

logger = logging.getLogger("affiliate")

affiliate_router = APIRouter(prefix="/affiliate", tags=["affiliate"])

# ===================
# CONSTANTS
# ===================
MIN_PAYOUT_AMOUNT = 100
MAX_PAYOUT_AMOUNT = 100000
COOKIE_EXPIRY_DAYS = 30
COMMISSION_STATUSES = ['pending', 'approved', 'paid', 'rejected']

# ===================
# SECURITY HELPERS
# ===================
async def log_affiliate_action(db, action: str, user_id: str, data: dict, success: bool = True):
    """Audit log for affiliate actions"""
    await db.affiliate_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": action,
        "user_id": user_id,
        "data": data,
        "success": success,
        "timestamp": datetime.utcnow()
    })

async def check_fraud_indicators(db, user_id: str, ip_address: str = None, device_id: str = None) -> dict:
    """Check for fraud indicators"""
    indicators = {
        "suspicious": False,
        "reasons": []
    }
    
    # Check for multiple accounts from same IP
    if ip_address:
        recent_attributions = await db.affiliate_attributions.count_documents({
            "metadata.ip_address": ip_address,
            "created_at": {"$gte": datetime.utcnow() - timedelta(hours=24)}
        })
        if recent_attributions > 10:
            indicators["suspicious"] = True
            indicators["reasons"].append("Multiple attributions from same IP")
    
    # Check for rapid conversions (potential click fraud)
    recent_conversions = await db.affiliate_commissions.count_documents({
        "referrer_id": user_id,
        "created_at": {"$gte": datetime.utcnow() - timedelta(hours=1)}
    })
    if recent_conversions > 5:
        indicators["suspicious"] = True
        indicators["reasons"].append("Rapid conversions detected")
    
    return indicators

def generate_secure_referral_code(user_id: str) -> str:
    """Generate unique, tamper-resistant referral code"""
    # Include timestamp and random component
    data = f"{user_id}{datetime.utcnow().timestamp()}{uuid.uuid4()}"
    return hashlib.sha256(data.encode()).hexdigest()[:8].upper()

async def get_current_user_affiliate(authorization: str = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from server import verify_jwt_token
    user_id = verify_jwt_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id

# ===================
# AFFILIATE ENDPOINTS
# ===================
@affiliate_router.post("/register")
async def register_affiliate(
    current_user: str = Depends(get_current_user_affiliate)
):
    """Register as affiliate with unique code constraint"""
    from server import db
    
    existing = await db.affiliate_accounts.find_one({"user_id": current_user})
    if existing:
        return {"referral_code": existing['referral_code'], "status": "already_registered"}
    
    # Generate unique referral code with retry
    referral_code = None
    for _ in range(5):
        code = generate_secure_referral_code(current_user)
        # Check uniqueness
        existing_code = await db.affiliate_accounts.find_one({"referral_code": code})
        if not existing_code:
            referral_code = code
            break
    
    if not referral_code:
        raise HTTPException(status_code=500, detail="Failed to generate unique code")
    
    account = AffiliateAccount(
        user_id=current_user,
        referral_code=referral_code
    )
    
    wallet = CommissionWallet(user_id=current_user)
    
    await db.affiliate_accounts.insert_one(account.model_dump())
    await db.commission_wallets.insert_one(wallet.model_dump())
    
    await db.users.update_one(
        {"id": current_user},
        {"$set": {"referral_code": referral_code, "is_affiliate": True}}
    )
    
    await log_affiliate_action(db, "register", current_user, {"referral_code": referral_code})
    
    return {"referral_code": referral_code, "status": "registered"}

@affiliate_router.get("/dashboard")
async def get_affiliate_dashboard(
    current_user: str = Depends(get_current_user_affiliate)
):
    """Get affiliate dashboard with stats"""
    from server import db
    
    account = await db.affiliate_accounts.find_one({"user_id": current_user})
    if not account:
        raise HTTPException(status_code=404, detail="Affiliate account not found. Please register first.")
    
    wallet = await db.commission_wallets.find_one({"user_id": current_user})
    
    # Get commission stats by status
    pipeline = [
        {"$match": {"referrer_id": current_user}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}, "total": {"$sum": "$commission_amount"}}}
    ]
    commission_stats = await db.affiliate_commissions.aggregate(pipeline).to_list(length=10)
    
    commissions = await db.affiliate_commissions.find(
        {"referrer_id": current_user}
    ).sort("created_at", -1).limit(10).to_list(length=10)
    
    pending_payouts = await db.payout_requests.find(
        {"user_id": current_user, "status": {"$in": ["pending", "processing"]}}
    ).to_list(length=10)
    
    # Clean MongoDB IDs
    for c in commissions:
        c.pop('_id', None)
    for p in pending_payouts:
        p.pop('_id', None)
    
    return {
        "referral_code": account['referral_code'],
        "total_referrals": account['total_referrals'],
        "total_bookings": account['total_bookings'],
        "commission_rate": account['commission_rate'],
        "commission_stats": {s['_id']: {"count": s['count'], "total": s['total']} for s in commission_stats},
        "wallet": {
            "balance": wallet['balance'] if wallet else 0,
            "pending": wallet['pending_balance'] if wallet else 0,
            "total_earned": wallet['total_earned'] if wallet else 0,
            "total_withdrawn": wallet['total_withdrawn'] if wallet else 0
        },
        "recent_commissions": commissions,
        "pending_payouts": pending_payouts
    }

@affiliate_router.post("/link/create")
async def create_affiliate_link(
    booking_type: Optional[str] = None,
    booking_item_id: Optional[str] = None,
    current_user: str = Depends(get_current_user_affiliate)
):
    """Create trackable affiliate link"""
    from server import db
    import os
    import html
    
    account = await db.affiliate_accounts.find_one({"user_id": current_user})
    if not account:
        raise HTTPException(status_code=404, detail="Affiliate account not found")
    
    base_url = os.getenv('APP_BASE_URL', 'https://aventaro.com')
    
    # Sanitize inputs
    if booking_type:
        booking_type = html.escape(booking_type)[:50]
    if booking_item_id:
        booking_item_id = html.escape(booking_item_id)[:100]
    
    # Build URL
    if booking_item_id:
        url = f"{base_url}/booking/{booking_type}/{booking_item_id}?ref={account['referral_code']}"
    elif booking_type:
        url = f"{base_url}/booking/{booking_type}?ref={account['referral_code']}"
    else:
        url = f"{base_url}?ref={account['referral_code']}"
    
    link = AffiliateLink(
        user_id=current_user,
        referral_code=account['referral_code'],
        booking_type=booking_type,
        booking_item_id=booking_item_id,
        url=url
    )
    
    await db.affiliate_links.insert_one(link.model_dump())
    
    return {"link_id": link.id, "url": url, "referral_code": account['referral_code']}

@affiliate_router.post("/track/{referral_code}")
async def track_affiliate_click(
    referral_code: str,
    request: Request,
    visitor_id: Optional[str] = None,
    source_url: Optional[str] = None,
    response: Response = None
):
    """Track affiliate link click with fraud detection"""
    from server import db
    
    account = await db.affiliate_accounts.find_one({"referral_code": referral_code})
    if not account:
        raise HTTPException(status_code=404, detail="Invalid referral code")
    
    # Get client IP
    ip_address = request.client.host if request.client else None
    
    # Check fraud indicators
    fraud_check = await check_fraud_indicators(db, account['user_id'], ip_address)
    if fraud_check['suspicious']:
        logger.warning(f"Suspicious affiliate activity: {fraud_check['reasons']}")
    
    if not visitor_id:
        visitor_id = str(uuid.uuid4())
    
    attribution = AffiliateAttribution(
        visitor_id=visitor_id,
        referral_code=referral_code,
        referrer_id=account['user_id'],
        source_url=source_url[:500] if source_url else "",
        expires_at=datetime.utcnow() + timedelta(days=COOKIE_EXPIRY_DAYS)
    )
    attribution_dict = attribution.model_dump()
    attribution_dict['metadata'] = {
        "ip_address": ip_address,
        "suspicious": fraud_check['suspicious']
    }
    
    await db.affiliate_attributions.insert_one(attribution_dict)
    
    # Update link clicks
    await db.affiliate_links.update_one(
        {"referral_code": referral_code},
        {"$inc": {"clicks": 1}}
    )
    
    # Set secure cookie
    if response:
        response.set_cookie(
            key="affiliate_ref",
            value=referral_code,
            max_age=COOKIE_EXPIRY_DAYS * 24 * 60 * 60,
            httponly=True,
            secure=True,
            samesite="lax"
        )
    
    return {"visitor_id": visitor_id, "attribution_id": attribution.id, "expires_in_days": COOKIE_EXPIRY_DAYS}

@affiliate_router.post("/attribute-booking")
async def attribute_booking_to_affiliate(
    booking_id: str,
    referral_code: str,
    current_user: str = Depends(get_current_user_affiliate)
):
    """Attribute a booking to an affiliate with validation"""
    from server import db
    
    # Get affiliate account
    account = await db.affiliate_accounts.find_one({"referral_code": referral_code})
    if not account:
        return {"attributed": False, "reason": "Invalid referral code"}
    
    # CRITICAL: Prevent self-referral
    if account['user_id'] == current_user:
        await log_affiliate_action(db, "self_referral_attempt", current_user, {
            "booking_id": booking_id,
            "referral_code": referral_code
        }, success=False)
        return {"attributed": False, "reason": "Self-referral not allowed"}
    
    # Get booking
    booking = await db.bookings.find_one({"id": booking_id, "user_id": current_user})
    if not booking:
        return {"attributed": False, "reason": "Booking not found"}
    
    # Check if already attributed
    if booking.get('referrer_user_id'):
        return {"attributed": False, "reason": "Already attributed"}
    
    # IMPORTANT: Only attribute if booking is NOT yet paid
    # Commission is created ONLY after payment success (in payment verification)
    if booking.get('payment_status') == 'paid':
        return {"attributed": False, "reason": "Cannot attribute after payment"}
    
    # Calculate commission
    commission_amount = calculate_commission(booking.get('amount', 0), account['commission_rate'])
    
    # Update booking with affiliate info (commission created after payment)
    await db.bookings.update_one(
        {"id": booking_id},
        {"$set": {
            "referred_by_code": referral_code,
            "referrer_user_id": account['user_id'],
            "affiliate_commission": commission_amount
        }}
    )
    
    # Update attribution record
    await db.affiliate_attributions.update_one(
        {"referral_code": referral_code, "converted": False},
        {"$set": {"converted": True, "conversion_booking_id": booking_id}}
    )
    
    await log_affiliate_action(db, "booking_attributed", account['user_id'], {
        "booking_id": booking_id,
        "referee_id": current_user,
        "commission_amount": commission_amount
    })
    
    return {"attributed": True, "commission_amount": commission_amount, "note": "Commission will be credited after payment"}

@affiliate_router.post("/payout/request")
async def request_payout(
    amount: float,
    payout_method: str,
    account_details: dict,
    current_user: str = Depends(get_current_user_affiliate)
):
    """Request payout with validation (requires admin approval)"""
    from server import db
    
    # Validate payout method
    valid_methods = ['bank_transfer', 'upi', 'paypal']
    if payout_method not in valid_methods:
        raise HTTPException(status_code=400, detail=f"Invalid payout method. Use: {valid_methods}")
    
    wallet = await db.commission_wallets.find_one({"user_id": current_user})
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    # Balance check
    if wallet['balance'] < amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    # Min/max validation
    if amount < MIN_PAYOUT_AMOUNT:
        raise HTTPException(status_code=400, detail=f"Minimum payout is {MIN_PAYOUT_AMOUNT}")
    
    if amount > MAX_PAYOUT_AMOUNT:
        raise HTTPException(status_code=400, detail=f"Maximum payout is {MAX_PAYOUT_AMOUNT}")
    
    # Check for pending payouts
    pending = await db.payout_requests.find_one({
        "user_id": current_user,
        "status": {"$in": ["pending", "processing"]}
    })
    if pending:
        raise HTTPException(status_code=400, detail="You have a pending payout request")
    
    payout = PayoutRequest(
        user_id=current_user,
        amount=amount,
        payout_method=payout_method,
        account_details=account_details,
        status="pending"  # Requires admin approval
    )
    
    await db.payout_requests.insert_one(payout.model_dump())
    
    # Hold amount (deduct from available, don't mark as withdrawn yet)
    await db.commission_wallets.update_one(
        {"user_id": current_user},
        {
            "$inc": {"balance": -amount, "pending_balance": amount},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    await log_affiliate_action(db, "payout_requested", current_user, {
        "amount": amount,
        "method": payout_method
    })
    
    return {
        "payout_id": payout.id,
        "status": "pending",
        "amount": amount,
        "message": "Payout request submitted for admin approval"
    }

@affiliate_router.get("/commissions")
async def get_commissions(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    current_user: str = Depends(get_current_user_affiliate)
):
    """Get commission history with pagination"""
    from server import db
    
    # Validate status
    if status and status not in COMMISSION_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Use: {COMMISSION_STATUSES}")
    
    limit = min(limit, 50)
    page = max(page, 1)
    
    query = {"referrer_id": current_user}
    if status:
        query["status"] = status
    
    total = await db.affiliate_commissions.count_documents(query)
    skip = (page - 1) * limit
    
    commissions = await db.affiliate_commissions.find(query).sort(
        "created_at", -1
    ).skip(skip).limit(limit).to_list(length=limit)
    
    for c in commissions:
        c.pop('_id', None)
    
    return {
        "commissions": commissions,
        "total": total,
        "page": page,
        "has_more": (skip + len(commissions)) < total
    }

@affiliate_router.get("/wallet")
async def get_wallet(
    current_user: str = Depends(get_current_user_affiliate)
):
    """Get commission wallet balance"""
    from server import db
    
    wallet = await db.commission_wallets.find_one({"user_id": current_user})
    if not wallet:
        return {"balance": 0, "pending": 0, "total_earned": 0, "total_withdrawn": 0}
    
    return {
        "balance": wallet['balance'],
        "pending": wallet['pending_balance'],
        "total_earned": wallet['total_earned'],
        "total_withdrawn": wallet['total_withdrawn']
    }

# ===================
# ADMIN ENDPOINTS
# ===================
@affiliate_router.post("/admin/commission/{commission_id}/approve")
async def admin_approve_commission(
    commission_id: str,
    current_user: str = Depends(get_current_user_affiliate)
):
    """Admin: Approve pending commission"""
    from server import db
    
    # TODO: Add proper admin role check
    user = await db.users.find_one({"id": current_user})
    if not user or not user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    commission = await db.affiliate_commissions.find_one({"id": commission_id})
    if not commission:
        raise HTTPException(status_code=404, detail="Commission not found")
    
    if commission['status'] != 'pending':
        raise HTTPException(status_code=400, detail="Commission is not pending")
    
    # Update commission status
    await db.affiliate_commissions.update_one(
        {"id": commission_id},
        {"$set": {
            "status": "approved",
            "approved_by": current_user,
            "approved_at": datetime.utcnow()
        }}
    )
    
    # Credit to wallet
    await db.commission_wallets.update_one(
        {"user_id": commission['referrer_id']},
        {
            "$inc": {
                "balance": commission['commission_amount'],
                "total_earned": commission['commission_amount']
            },
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    # Update affiliate stats
    await db.affiliate_accounts.update_one(
        {"user_id": commission['referrer_id']},
        {"$inc": {"total_bookings": 1}}
    )
    
    await log_affiliate_action(db, "commission_approved", current_user, {
        "commission_id": commission_id,
        "amount": commission['commission_amount'],
        "referrer_id": commission['referrer_id']
    })
    
    return {"status": "approved", "commission_id": commission_id}

@affiliate_router.post("/admin/payout/{payout_id}/process")
async def admin_process_payout(
    payout_id: str,
    transaction_ref: Optional[str] = None,
    current_user: str = Depends(get_current_user_affiliate)
):
    """Admin: Process payout request"""
    from server import db
    
    user = await db.users.find_one({"id": current_user})
    if not user or not user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    payout = await db.payout_requests.find_one({"id": payout_id})
    if not payout:
        raise HTTPException(status_code=404, detail="Payout request not found")
    
    if payout['status'] not in ['pending', 'processing']:
        raise HTTPException(status_code=400, detail="Payout already processed")
    
    # Update payout
    await db.payout_requests.update_one(
        {"id": payout_id},
        {"$set": {
            "status": "completed",
            "processed_at": datetime.utcnow(),
            "transaction_ref": transaction_ref
        }}
    )
    
    # Update wallet
    await db.commission_wallets.update_one(
        {"user_id": payout['user_id']},
        {
            "$inc": {
                "pending_balance": -payout['amount'],
                "total_withdrawn": payout['amount']
            },
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    await log_affiliate_action(db, "payout_processed", current_user, {
        "payout_id": payout_id,
        "amount": payout['amount'],
        "user_id": payout['user_id'],
        "transaction_ref": transaction_ref
    })
    
    return {"status": "completed", "payout_id": payout_id}
