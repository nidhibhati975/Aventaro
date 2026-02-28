"""
PAYMENT MODULE - Production Ready
Supports: Razorpay, Stripe, UPI, PayPal
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import uuid
import hashlib
import hmac
import qrcode
import io
import base64

class PaymentProvider(str, Enum):
    RAZORPAY = "razorpay"
    STRIPE = "stripe"
    UPI = "upi"
    PAYPAL = "paypal"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"

class PaymentMethod(str, Enum):
    CARD = "card"
    UPI = "upi"
    NETBANKING = "netbanking"
    WALLET = "wallet"
    PAYPAL = "paypal"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"

class Transaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    booking_id: Optional[str] = None
    amount: float
    currency: str = "INR"
    provider: PaymentProvider
    method: PaymentMethod
    status: PaymentStatus = PaymentStatus.PENDING
    idempotency_key: str
    provider_order_id: Optional[str] = None
    provider_payment_id: Optional[str] = None
    provider_signature: Optional[str] = None
    metadata: Dict[str, Any] = {}
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    refund_amount: Optional[float] = None
    refund_id: Optional[str] = None
    refunded_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

class UPIQRCode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transaction_id: str
    upi_id: str
    payee_name: str
    amount: float
    qr_type: str = "dynamic"  # static or dynamic
    qr_data: str
    qr_image_base64: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)

class RefundRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transaction_id: str
    booking_id: str
    user_id: str
    amount: float
    reason: str
    status: str = "pending"  # pending, approved, processed, rejected
    provider_refund_id: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PaymentCreateRequest(BaseModel):
    booking_id: str
    amount: float
    currency: str = "INR"
    provider: PaymentProvider
    method: PaymentMethod
    idempotency_key: str
    return_url: Optional[str] = None
    upi_id: Optional[str] = None  # For UPI intent
    affiliate_code: Optional[str] = None

class PaymentVerifyRequest(BaseModel):
    transaction_id: str
    provider_order_id: str
    provider_payment_id: str
    provider_signature: str

class RefundCreateRequest(BaseModel):
    transaction_id: str
    booking_id: str
    amount: Optional[float] = None  # Full refund if None
    reason: str

def generate_upi_qr(upi_id: str, payee_name: str, amount: float, transaction_id: str) -> tuple:
    """Generate UPI QR code"""
    upi_string = f"upi://pay?pa={upi_id}&pn={payee_name}&am={amount}&tr={transaction_id}&cu=INR"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(upi_string)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return upi_string, qr_base64

def verify_razorpay_signature(order_id: str, payment_id: str, signature: str, secret: str) -> bool:
    """Verify Razorpay payment signature"""
    msg = f"{order_id}|{payment_id}"
    generated = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(generated, signature)

def verify_stripe_webhook(payload: bytes, sig_header: str, webhook_secret: str) -> bool:
    """Verify Stripe webhook signature"""
    import stripe
    try:
        stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        return True
    except:
        return False
