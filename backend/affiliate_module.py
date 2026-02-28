"""
AFFILIATE MODULE - Production Ready
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid
import hashlib

class AffiliateAccount(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    referral_code: str
    total_referrals: int = 0
    total_bookings: int = 0
    total_earnings: float = 0.0
    pending_earnings: float = 0.0
    paid_earnings: float = 0.0
    commission_rate: float = 5.0  # Default 5%
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AffiliateCommission(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    referrer_id: str
    referee_id: str
    booking_id: str
    transaction_id: str
    booking_amount: float
    commission_rate: float
    commission_amount: float
    status: str = "pending"  # pending, approved, paid, rejected
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    payout_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CommissionWallet(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    balance: float = 0.0
    pending_balance: float = 0.0
    total_earned: float = 0.0
    total_withdrawn: float = 0.0
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class PayoutRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    amount: float
    payout_method: str  # bank_transfer, upi, paypal
    account_details: dict
    status: str = "pending"  # pending, processing, completed, failed
    processed_at: Optional[datetime] = None
    transaction_ref: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AffiliateLink(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    referral_code: str
    booking_type: Optional[str] = None  # hotel, flight, etc.
    booking_item_id: Optional[str] = None
    url: str
    clicks: int = 0
    conversions: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AffiliateAttribution(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    visitor_id: str  # Cookie/token based
    referral_code: str
    referrer_id: str
    source_url: str
    expires_at: datetime
    converted: bool = False
    conversion_booking_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

def generate_referral_code(user_id: str) -> str:
    """Generate unique referral code"""
    hash_input = f"{user_id}{datetime.utcnow().timestamp()}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:8].upper()

def calculate_commission(booking_amount: float, commission_rate: float) -> float:
    """Calculate commission amount"""
    return round(booking_amount * (commission_rate / 100), 2)
