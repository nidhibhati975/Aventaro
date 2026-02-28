"""
AVENTARO BOOKING MODULE - MODULAR EXTENSION
===========================================
This module extends Aventaro with Super Booking Hub capabilities.
DOES NOT modify existing Discover, Matches, Trips functionality.

New Features:
- Hotels, Flights, Villas, Apartments, Holiday Packages
- Intercity Cabs, Airport Cabs, Bus, Train booking
- Activities
- Global Payment System
- Affiliate/Referral tracking for bookings
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from decimal import Decimal

# =====================
# BOOKING MODELS (NEW)
# =====================

class BookingSearch(BaseModel):
    """Search parameters for any booking type"""
    service_type: str  # hotel, flight, villa, cab, bus, train, activity, apartment, package
    origin: Optional[str] = None  # For flights, cabs, buses, trains
    destination: str
    check_in_date: Optional[str] = None  # For hotels, villas
    check_out_date: Optional[str] = None
    departure_date: Optional[str] = None  # For flights, buses, trains
    return_date: Optional[str] = None
    guests: int = 1
    rooms: Optional[int] = 1
    class_type: Optional[str] = "economy"  # For flights: economy, business, first
    currency: str = "INR"
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    amenities: List[str] = []
    rating_min: Optional[float] = None
    page: int = 1
    limit: int = 20

class BookingItem(BaseModel):
    """Individual booking item (hotel, flight, etc.)"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_type: str  # hotel, flight, villa, etc.
    provider_id: str  # External API provider ID
    provider_name: str  # e.g., "MakeMyTrip", "Booking.com"
    name: str  # Hotel name, Flight number, etc.
    description: str
    location: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    check_in_date: Optional[str] = None
    check_out_date: Optional[str] = None
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    duration: Optional[str] = None
    price: float
    currency: str = "INR"
    original_price: Optional[float] = None  # For discounts
    commission_rate: float = 0.0  # Platform commission %
    images: List[str] = []
    amenities: List[str] = []
    rating: Optional[float] = None
    reviews_count: int = 0
    cancellation_policy: str = ""
    refund_policy: str = ""
    is_available: bool = True
    metadata: Dict[str, Any] = {}  # Flexible for service-specific data
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Booking(BaseModel):
    """Main booking record"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str  # References existing users collection
    booking_item_id: str
    service_type: str
    booking_status: str = "pending"  # pending, confirmed, cancelled, completed
    payment_status: str = "pending"  # pending, paid, failed, refunded
    payment_id: Optional[str] = None
    amount: float
    currency: str = "INR"
    commission_amount: float = 0.0
    
    # Guest details
    guest_name: str
    guest_email: str
    guest_phone: str
    guest_count: int = 1
    
    # Booking specifics
    check_in_date: Optional[str] = None
    check_out_date: Optional[str] = None
    departure_date: Optional[str] = None
    return_date: Optional[str] = None
    
    # Special requests
    special_requests: Optional[str] = None
    
    # Cancellation/Refund
    cancellation_requested_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    refund_amount: Optional[float] = None
    refund_status: Optional[str] = None  # pending, approved, processed
    
    # Referral tracking
    referred_by_code: Optional[str] = None
    referrer_user_id: Optional[str] = None
    affiliate_commission: float = 0.0
    
    # Trip attachment (NEW: Link to existing Trips)
    attached_trip_id: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    confirmed_at: Optional[datetime] = None

class Payment(BaseModel):
    """Global payment record (extends existing wallet)"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    booking_id: Optional[str] = None  # For booking payments
    payment_method: str  # card, upi, wallet, bank_transfer, paypal, apple_pay, google_pay
    payment_provider: str  # razorpay, stripe, paypal, etc.
    amount: float
    currency: str = "INR"
    status: str = "pending"  # pending, completed, failed, refunded
    
    # Provider IDs
    provider_order_id: Optional[str] = None
    provider_payment_id: Optional[str] = None
    provider_signature: Optional[str] = None
    
    # Card details (masked)
    card_last4: Optional[str] = None
    card_brand: Optional[str] = None
    
    # UPI details
    upi_id: Optional[str] = None
    upi_transaction_id: Optional[str] = None
    
    # Refund tracking
    refund_amount: Optional[float] = None
    refund_reason: Optional[str] = None
    refunded_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = {}
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

class BookingReview(BaseModel):
    """Reviews for bookings"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    booking_id: str
    user_id: str
    service_type: str
    provider_name: str
    rating: float  # 1-5
    title: str
    review_text: str
    images: List[str] = []
    helpful_count: int = 0
    is_verified_booking: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class BookingReferral(BaseModel):
    """Affiliate/Referral tracking for bookings"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    referrer_user_id: str  # User who referred
    referee_user_id: str  # User who booked using referral
    booking_id: str
    referral_code: str
    commission_amount: float
    commission_rate: float
    commission_status: str = "pending"  # pending, approved, paid
    
    # Admin approval
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    
    # Payout
    paid_at: Optional[datetime] = None
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class RefundRequest(BaseModel):
    """Refund management"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    booking_id: str
    user_id: str
    payment_id: str
    refund_amount: float
    refund_reason: str
    status: str = "pending"  # pending, approved, rejected, processed
    
    # Processing
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    
    # Refund details
    refund_method: Optional[str] = None  # same_as_payment, bank_transfer, wallet
    refund_reference: Optional[str] = None
    processed_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

# =====================
# REQUEST/RESPONSE MODELS
# =====================

class BookingCreateRequest(BaseModel):
    booking_item_id: str
    service_type: str
    guest_name: str
    guest_email: str
    guest_phone: str
    guest_count: int = 1
    check_in_date: Optional[str] = None
    check_out_date: Optional[str] = None
    departure_date: Optional[str] = None
    return_date: Optional[str] = None
    special_requests: Optional[str] = None
    referral_code: Optional[str] = None
    attach_to_trip_id: Optional[str] = None
    payment_method: str

class PaymentCreateRequest(BaseModel):
    booking_id: str
    payment_method: str  # card, upi, wallet, etc.
    amount: float
    currency: str = "INR"
    return_url: Optional[str] = None

class PaymentVerifyRequest(BaseModel):
    payment_id: str
    provider_order_id: str
    provider_payment_id: str
    provider_signature: str

class ReviewCreateRequest(BaseModel):
    booking_id: str
    rating: float
    title: str
    review_text: str
    images: List[str] = []

class RefundCreateRequest(BaseModel):
    booking_id: str
    refund_reason: str
    refund_amount: Optional[float] = None  # If partial refund

# =====================
# RESPONSE MODELS
# =====================

class BookingSearchResponse(BaseModel):
    results: List[BookingItem]
    total: int
    page: int
    limit: int
    has_more: bool

class BookingResponse(BaseModel):
    booking: Booking
    booking_item: BookingItem
    payment_required: bool
    payment_amount: float

class PaymentOrderResponse(BaseModel):
    order_id: str
    amount: float
    currency: str
    payment_methods: List[str]
    redirect_url: Optional[str] = None

# =====================
# WEBHOOK MODELS
# =====================

class WebhookEvent(BaseModel):
    """Generic webhook event handler"""
    event_type: str  # payment.success, payment.failed, booking.confirmed, etc.
    provider: str  # razorpay, stripe, etc.
    data: Dict[str, Any]
    signature: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
