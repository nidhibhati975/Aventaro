"""
AFFILIATE ROUTES - Production Ready
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Response
from typing import Optional
from datetime import datetime, timedelta
import uuid
from affiliate_module import *

affiliate_router = APIRouter(prefix="/affiliate", tags=["affiliate"])

async def get_current_user_affiliate(authorization: str = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from server import verify_jwt_token
    user_id = verify_jwt_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id

@affiliate_router.post("/register")
async def register_affiliate(
    current_user: str = Depends(get_current_user_affiliate)
):
    """Register as affiliate"""
    from server import db
    
    existing = await db.affiliate_accounts.find_one({"user_id": current_user})
    if existing:
        return {"referral_code": existing['referral_code'], "status": "already_registered"}
    
    referral_code = generate_referral_code(current_user)
    
    account = AffiliateAccount(
        user_id=current_user,
        referral_code=referral_code
    )
    
    wallet = CommissionWallet(user_id=current_user)
    
    await db.affiliate_accounts.insert_one(account.model_dump())
    await db.commission_wallets.insert_one(wallet.model_dump())
    
    # Update user with referral code
    await db.users.update_one(
        {"id": current_user},
        {"$set": {"referral_code": referral_code, "is_affiliate": True}}
    )
    
    return {"referral_code": referral_code, "status": "registered"}

@affiliate_router.get("/dashboard")
async def get_affiliate_dashboard(
    current_user: str = Depends(get_current_user_affiliate)
):
    """Get affiliate dashboard data"""
    from server import db
    
    account = await db.affiliate_accounts.find_one({"user_id": current_user})
    if not account:
        raise HTTPException(status_code=404, detail="Affiliate account not found")
    
    wallet = await db.commission_wallets.find_one({"user_id": current_user})
    
    # Get recent commissions
    commissions = await db.affiliate_commissions.find(
        {"referrer_id": current_user}
    ).sort("created_at", -1).limit(10).to_list(length=10)
    
    # Get pending payouts
    pending_payouts = await db.payout_requests.find(
        {"user_id": current_user, "status": "pending"}
    ).to_list(length=10)
    
    return {
        "referral_code": account['referral_code'],
        "total_referrals": account['total_referrals'],
        "total_bookings": account['total_bookings'],
        "commission_rate": account['commission_rate'],
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
    
    account = await db.affiliate_accounts.find_one({"user_id": current_user})
    if not account:
        raise HTTPException(status_code=404, detail="Affiliate account not found")
    
    base_url = os.getenv('APP_BASE_URL', 'https://aventaro.com')
    
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
    visitor_id: Optional[str] = None,
    source_url: Optional[str] = None,
    response: Response = None
):
    """Track affiliate link click and set attribution cookie"""
    from server import db
    
    account = await db.affiliate_accounts.find_one({"referral_code": referral_code})
    if not account:
        raise HTTPException(status_code=404, detail="Invalid referral code")
    
    # Generate visitor ID if not provided
    if not visitor_id:
        visitor_id = str(uuid.uuid4())
    
    attribution = AffiliateAttribution(
        visitor_id=visitor_id,
        referral_code=referral_code,
        referrer_id=account['user_id'],
        source_url=source_url or "",
        expires_at=datetime.utcnow() + timedelta(days=30)
    )
    
    await db.affiliate_attributions.insert_one(attribution.model_dump())
    
    # Update link clicks
    await db.affiliate_links.update_one(
        {"referral_code": referral_code},
        {"$inc": {"clicks": 1}}
    )
    
    # Set cookie in response
    if response:
        response.set_cookie(
            key="affiliate_ref",
            value=referral_code,
            max_age=30*24*60*60,  # 30 days
            httponly=True
        )
    
    return {"visitor_id": visitor_id, "attribution_id": attribution.id}

@affiliate_router.post("/attribute-booking")
async def attribute_booking_to_affiliate(
    booking_id: str,
    referral_code: str,
    current_user: str = Depends(get_current_user_affiliate)
):
    """Attribute a booking to an affiliate"""
    from server import db
    
    # Get affiliate account
    account = await db.affiliate_accounts.find_one({"referral_code": referral_code})
    if not account:
        return {"attributed": False, "reason": "Invalid referral code"}
    
    # Don't allow self-referral
    if account['user_id'] == current_user:
        return {"attributed": False, "reason": "Self-referral not allowed"}
    
    # Get booking
    booking = await db.bookings.find_one({"id": booking_id, "user_id": current_user})
    if not booking:
        return {"attributed": False, "reason": "Booking not found"}
    
    # Check if already attributed
    if booking.get('referrer_user_id'):
        return {"attributed": False, "reason": "Already attributed"}
    
    # Calculate commission
    commission_amount = calculate_commission(booking['amount'], account['commission_rate'])
    
    # Update booking
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
        {"$set": {"converted": True, "conversion_booking_id": booking_id}},
        upsert=False
    )
    
    return {"attributed": True, "commission_amount": commission_amount}

@affiliate_router.post("/payout/request")
async def request_payout(
    amount: float,
    payout_method: str,
    account_details: dict,
    current_user: str = Depends(get_current_user_affiliate)
):
    """Request payout of commission earnings"""
    from server import db
    
    wallet = await db.commission_wallets.find_one({"user_id": current_user})
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    if wallet['balance'] < amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    if amount < 100:  # Minimum payout
        raise HTTPException(status_code=400, detail="Minimum payout is 100")
    
    payout = PayoutRequest(
        user_id=current_user,
        amount=amount,
        payout_method=payout_method,
        account_details=account_details
    )
    
    await db.payout_requests.insert_one(payout.model_dump())
    
    # Deduct from balance, add to pending
    await db.commission_wallets.update_one(
        {"user_id": current_user},
        {
            "$inc": {"balance": -amount},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    return {"payout_id": payout.id, "status": "pending", "amount": amount}

@affiliate_router.get("/commissions")
async def get_commissions(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    current_user: str = Depends(get_current_user_affiliate)
):
    """Get commission history"""
    from server import db
    
    query = {"referrer_id": current_user}
    if status:
        query["status"] = status
    
    total = await db.affiliate_commissions.count_documents(query)
    skip = (page - 1) * limit
    
    commissions = await db.affiliate_commissions.find(query).sort(
        "created_at", -1
    ).skip(skip).limit(limit).to_list(length=limit)
    
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
