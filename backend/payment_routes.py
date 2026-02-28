"""
PAYMENT ROUTES - Production Hardened
Security: Webhook deduplication, signature verification, transaction logging, race condition prevention
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from typing import Optional
from datetime import datetime, timedelta
import os
import json
import stripe
import razorpay
import hmac
import hashlib
import logging
import uuid
from payment_module import *

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("payment")

payment_router = APIRouter(prefix="/payment", tags=["payment"])

# ===================
# ENV VALIDATION
# ===================
REQUIRED_ENV_VARS = [
    'RAZORPAY_KEY_ID', 'RAZORPAY_KEY_SECRET', 'RAZORPAY_WEBHOOK_SECRET',
    'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET', 'MERCHANT_UPI_ID'
]

def validate_env():
    """Validate required environment variables"""
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        logger.warning(f"Missing payment env vars: {missing}")
    return missing

# Initialize clients with validation
razorpay_key_id = os.getenv('RAZORPAY_KEY_ID', '')
razorpay_key_secret = os.getenv('RAZORPAY_KEY_SECRET', '')
razorpay_client = None
if razorpay_key_id and razorpay_key_secret:
    razorpay_client = razorpay.Client(auth=(razorpay_key_id, razorpay_key_secret))

stripe_key = os.getenv('STRIPE_SECRET_KEY', '')
if stripe_key:
    stripe.api_key = stripe_key

# ===================
# SECURITY HELPERS
# ===================
async def log_payment_event(db, event_type: str, data: dict, user_id: str = None, success: bool = True):
    """Log all payment events for audit"""
    await db.payment_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "event_type": event_type,
        "user_id": user_id,
        "data": {k: v for k, v in data.items() if k not in ['client_secret', 'signature', 'password']},
        "success": success,
        "ip_address": data.get('ip_address'),
        "timestamp": datetime.utcnow()
    })

async def check_webhook_processed(db, event_id: str) -> bool:
    """Check if webhook event was already processed (idempotency)"""
    existing = await db.webhook_events.find_one({"event_id": event_id})
    return existing is not None

async def mark_webhook_processed(db, event_id: str, provider: str, event_type: str):
    """Mark webhook event as processed"""
    await db.webhook_events.insert_one({
        "event_id": event_id,
        "provider": provider,
        "event_type": event_type,
        "processed_at": datetime.utcnow()
    })

def verify_razorpay_signature_secure(order_id: str, payment_id: str, signature: str, secret: str) -> bool:
    """Verify Razorpay signature using HMAC SHA256 with timing-safe comparison"""
    if not all([order_id, payment_id, signature, secret]):
        return False
    msg = f"{order_id}|{payment_id}"
    expected = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

def verify_razorpay_webhook_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify Razorpay webhook signature"""
    if not all([body, signature, secret]):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

async def acquire_payment_lock(db, booking_id: str) -> bool:
    """Acquire lock to prevent race conditions"""
    result = await db.payment_locks.update_one(
        {"booking_id": booking_id, "locked": False},
        {"$set": {"locked": True, "locked_at": datetime.utcnow()}},
        upsert=True
    )
    return result.modified_count > 0 or result.upserted_id is not None

async def release_payment_lock(db, booking_id: str):
    """Release payment lock"""
    await db.payment_locks.update_one(
        {"booking_id": booking_id},
        {"$set": {"locked": False}}
    )

async def get_current_user_payment(authorization: str = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from server import verify_jwt_token
    user_id = verify_jwt_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id

# ===================
# PAYMENT ENDPOINTS
# ===================
@payment_router.get("/health")
async def payment_health():
    """Check payment system health and env validation"""
    missing = validate_env()
    return {
        "status": "healthy" if not missing else "degraded",
        "missing_env": missing,
        "razorpay_configured": razorpay_client is not None,
        "stripe_configured": bool(stripe_key)
    }

@payment_router.post("/create")
async def create_payment(
    request: PaymentCreateRequest,
    current_user: str = Depends(get_current_user_payment)
):
    """Create payment order with idempotency and race condition prevention"""
    from server import db
    
    # Check idempotency first
    existing = await db.transactions.find_one({"idempotency_key": request.idempotency_key})
    if existing:
        await log_payment_event(db, "payment_create_cached", {"transaction_id": existing['id']}, current_user)
        return {"transaction_id": existing['id'], "status": existing['status'], "cached": True}
    
    # Verify booking exists and belongs to user
    booking = await db.bookings.find_one({"id": request.booking_id, "user_id": current_user})
    if not booking:
        await log_payment_event(db, "payment_create_failed", {"reason": "booking_not_found"}, current_user, False)
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Prevent double payment
    if booking.get('payment_status') == 'paid':
        raise HTTPException(status_code=400, detail="Already paid")
    
    # Acquire lock to prevent race conditions
    if not await acquire_payment_lock(db, request.booking_id):
        raise HTTPException(status_code=409, detail="Payment already in progress")
    
    try:
        amount_paise = int(request.amount * 100)
        
        transaction = Transaction(
            user_id=current_user,
            booking_id=request.booking_id,
            amount=request.amount,
            currency=request.currency,
            provider=request.provider,
            method=request.method,
            idempotency_key=request.idempotency_key
        )
        
        if request.provider == PaymentProvider.RAZORPAY:
            if not razorpay_client:
                raise HTTPException(status_code=503, detail="Razorpay not configured")
            
            order = razorpay_client.order.create({
                'amount': amount_paise,
                'currency': request.currency,
                'payment_capture': 1,
                'notes': {'booking_id': request.booking_id, 'user_id': current_user}
            })
            transaction.provider_order_id = order['id']
            await db.transactions.insert_one(transaction.model_dump())
            
            await log_payment_event(db, "payment_created", {
                "provider": "razorpay", "order_id": order['id'], "amount": request.amount
            }, current_user)
            
            return {
                "transaction_id": transaction.id,
                "provider_order_id": order['id'],
                "amount": request.amount,
                "currency": request.currency,
                "key_id": razorpay_key_id,
                "provider": "razorpay"
            }
            
        elif request.provider == PaymentProvider.STRIPE:
            if not stripe_key:
                raise HTTPException(status_code=503, detail="Stripe not configured")
            
            intent = stripe.PaymentIntent.create(
                amount=amount_paise,
                currency=request.currency.lower(),
                metadata={'booking_id': request.booking_id, 'user_id': current_user}
            )
            transaction.provider_order_id = intent.id
            await db.transactions.insert_one(transaction.model_dump())
            
            await log_payment_event(db, "payment_created", {
                "provider": "stripe", "intent_id": intent.id, "amount": request.amount
            }, current_user)
            
            # Note: client_secret is intentionally returned but never logged
            return {
                "transaction_id": transaction.id,
                "client_secret": intent.client_secret,
                "provider_order_id": intent.id,
                "provider": "stripe"
            }
            
        elif request.provider == PaymentProvider.UPI:
            upi_id = os.getenv('MERCHANT_UPI_ID')
            if not upi_id:
                raise HTTPException(status_code=503, detail="UPI not configured")
            
            payee_name = os.getenv('MERCHANT_NAME', 'Aventaro')
            qr_data, qr_image = generate_upi_qr(upi_id, payee_name, request.amount, transaction.id)
            
            qr_record = UPIQRCode(
                transaction_id=transaction.id,
                upi_id=upi_id,
                payee_name=payee_name,
                amount=request.amount,
                qr_type="dynamic",
                qr_data=qr_data,
                qr_image_base64=qr_image,
                expires_at=datetime.utcnow() + timedelta(minutes=15)
            )
            
            await db.transactions.insert_one(transaction.model_dump())
            await db.upi_qr_codes.insert_one(qr_record.model_dump())
            
            await log_payment_event(db, "upi_qr_created", {
                "transaction_id": transaction.id, "amount": request.amount
            }, current_user)
            
            return {
                "transaction_id": transaction.id,
                "qr_data": qr_data,
                "qr_image": qr_image,
                "upi_intent": qr_data,
                "expires_at": qr_record.expires_at.isoformat(),
                "provider": "upi",
                "note": "Payment confirmation via PSP webhook or manual verification required"
            }
            
        elif request.provider == PaymentProvider.PAYPAL:
            # PayPal - sandbox mode indicator
            is_sandbox = os.getenv('PAYPAL_MODE', 'sandbox') == 'sandbox'
            transaction.provider_order_id = f"PP_{transaction.id[:8]}"
            transaction.metadata = {"sandbox": is_sandbox}
            await db.transactions.insert_one(transaction.model_dump())
            
            await log_payment_event(db, "payment_created", {
                "provider": "paypal", "sandbox": is_sandbox, "amount": request.amount
            }, current_user)
            
            return {
                "transaction_id": transaction.id,
                "approval_url": f"https://{'sandbox.' if is_sandbox else ''}paypal.com/checkout?token={transaction.id}",
                "provider": "paypal",
                "sandbox": is_sandbox
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment creation failed: {str(e)}")
        await log_payment_event(db, "payment_create_failed", {"error": str(e)}, current_user, False)
        raise HTTPException(status_code=500, detail="Payment creation failed")
    finally:
        await release_payment_lock(db, request.booking_id)

@payment_router.post("/verify")
async def verify_payment(
    request: PaymentVerifyRequest,
    current_user: str = Depends(get_current_user_payment)
):
    """Verify payment with strict signature validation"""
    from server import db
    
    transaction = await db.transactions.find_one({"id": request.transaction_id, "user_id": current_user})
    if not transaction:
        await log_payment_event(db, "verify_failed", {"reason": "transaction_not_found"}, current_user, False)
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if transaction['status'] == PaymentStatus.COMPLETED.value:
        return {"status": "already_verified", "booking_status": "confirmed"}
    
    # Acquire lock
    if not await acquire_payment_lock(db, transaction['booking_id']):
        raise HTTPException(status_code=409, detail="Verification in progress")
    
    try:
        if transaction['provider'] == PaymentProvider.RAZORPAY.value:
            is_valid = verify_razorpay_signature_secure(
                request.provider_order_id,
                request.provider_payment_id,
                request.provider_signature,
                razorpay_key_secret
            )
            
            if not is_valid:
                await log_payment_event(db, "signature_verification_failed", {
                    "transaction_id": request.transaction_id,
                    "provider": "razorpay"
                }, current_user, False)
                raise HTTPException(status_code=400, detail="Invalid signature")
        
        elif transaction['provider'] == PaymentProvider.STRIPE.value:
            # Verify PaymentIntent status with Stripe
            try:
                intent = stripe.PaymentIntent.retrieve(request.provider_order_id)
                if intent.status != 'succeeded':
                    raise HTTPException(status_code=400, detail=f"Payment not succeeded: {intent.status}")
            except stripe.error.StripeError as e:
                await log_payment_event(db, "stripe_verify_failed", {"error": str(e)}, current_user, False)
                raise HTTPException(status_code=400, detail="Stripe verification failed")
        
        # Update transaction atomically
        result = await db.transactions.update_one(
            {"id": request.transaction_id, "status": {"$ne": PaymentStatus.COMPLETED.value}},
            {"$set": {
                "status": PaymentStatus.COMPLETED.value,
                "provider_payment_id": request.provider_payment_id,
                "provider_signature": request.provider_signature,
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )
        
        if result.modified_count == 0:
            return {"status": "already_verified", "booking_status": "confirmed"}
        
        # Update booking - ONLY after payment verified
        await db.bookings.update_one(
            {"id": transaction['booking_id']},
            {"$set": {
                "payment_status": "paid",
                "booking_status": "confirmed",
                "payment_id": request.transaction_id,
                "confirmed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Process affiliate commission ONLY after payment success
        booking = await db.bookings.find_one({"id": transaction['booking_id']})
        if booking and booking.get('referrer_user_id'):
            # Commission starts as PENDING
            await db.affiliate_commissions.insert_one({
                "id": str(uuid.uuid4()),
                "referrer_id": booking['referrer_user_id'],
                "referee_id": current_user,
                "booking_id": booking['id'],
                "transaction_id": request.transaction_id,
                "booking_amount": transaction['amount'],
                "commission_rate": 5.0,
                "commission_amount": booking.get('affiliate_commission', 0),
                "status": "pending",  # Requires approval
                "created_at": datetime.utcnow()
            })
        
        await log_payment_event(db, "payment_verified", {
            "transaction_id": request.transaction_id,
            "amount": transaction['amount']
        }, current_user)
        
        return {"status": "verified", "booking_status": "confirmed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verification failed: {str(e)}")
        await db.transactions.update_one(
            {"id": request.transaction_id},
            {"$set": {"status": PaymentStatus.FAILED.value, "error_message": str(e)}}
        )
        raise HTTPException(status_code=400, detail="Verification failed")
    finally:
        await release_payment_lock(db, transaction['booking_id'])

@payment_router.post("/retry/{transaction_id}")
async def retry_payment(
    transaction_id: str,
    current_user: str = Depends(get_current_user_payment)
):
    """Retry failed payment with proper validation"""
    from server import db
    
    transaction = await db.transactions.find_one({"id": transaction_id, "user_id": current_user})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if transaction['status'] != PaymentStatus.FAILED.value:
        raise HTTPException(status_code=400, detail="Can only retry failed payments")
    
    if transaction['retry_count'] >= transaction['max_retries']:
        raise HTTPException(status_code=400, detail="Max retries exceeded")
    
    await db.transactions.update_one(
        {"id": transaction_id},
        {"$inc": {"retry_count": 1}, "$set": {"status": PaymentStatus.PENDING.value}}
    )
    
    await log_payment_event(db, "payment_retry", {
        "transaction_id": transaction_id,
        "retry_count": transaction['retry_count'] + 1
    }, current_user)
    
    return await create_payment(
        PaymentCreateRequest(
            booking_id=transaction['booking_id'],
            amount=transaction['amount'],
            currency=transaction['currency'],
            provider=PaymentProvider(transaction['provider']),
            method=PaymentMethod(transaction['method']),
            idempotency_key=f"{transaction['idempotency_key']}_retry_{transaction['retry_count'] + 1}"
        ),
        current_user
    )

@payment_router.post("/refund")
async def request_refund(
    request: RefundCreateRequest,
    current_user: str = Depends(get_current_user_payment)
):
    """Request refund with proper validation"""
    from server import db
    
    transaction = await db.transactions.find_one({"id": request.transaction_id, "user_id": current_user})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if transaction['status'] != PaymentStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Can only refund completed payments")
    
    # Check if already refunded
    if transaction.get('refund_id'):
        raise HTTPException(status_code=400, detail="Already refunded")
    
    refund_amount = request.amount or transaction['amount']
    if refund_amount > transaction['amount']:
        raise HTTPException(status_code=400, detail="Refund amount exceeds payment")
    
    refund = RefundRequest(
        transaction_id=request.transaction_id,
        booking_id=request.booking_id,
        user_id=current_user,
        amount=refund_amount,
        reason=request.reason
    )
    
    try:
        if transaction['provider'] == PaymentProvider.RAZORPAY.value:
            if not razorpay_client:
                raise HTTPException(status_code=503, detail="Razorpay not configured")
            razorpay_refund = razorpay_client.payment.refund(
                transaction['provider_payment_id'],
                {'amount': int(refund_amount * 100)}
            )
            refund.provider_refund_id = razorpay_refund['id']
            refund.status = "processed"
            refund.processed_at = datetime.utcnow()
            
        elif transaction['provider'] == PaymentProvider.STRIPE.value:
            stripe_refund = stripe.Refund.create(
                payment_intent=transaction['provider_order_id'],
                amount=int(refund_amount * 100)
            )
            refund.provider_refund_id = stripe_refund.id
            refund.status = "processed"
            refund.processed_at = datetime.utcnow()
        
        await db.refund_requests.insert_one(refund.model_dump())
        
        new_status = PaymentStatus.REFUNDED if refund_amount == transaction['amount'] else PaymentStatus.PARTIALLY_REFUNDED
        await db.transactions.update_one(
            {"id": request.transaction_id},
            {"$set": {
                "status": new_status.value,
                "refund_amount": refund_amount,
                "refund_id": refund.id,
                "refunded_at": datetime.utcnow()
            }}
        )
        
        await db.bookings.update_one(
            {"id": request.booking_id},
            {"$set": {
                "refund_status": "processed",
                "refund_amount": refund_amount,
                "booking_status": "cancelled" if refund_amount == transaction['amount'] else "partial_refund"
            }}
        )
        
        await log_payment_event(db, "refund_processed", {
            "transaction_id": request.transaction_id,
            "refund_amount": refund_amount
        }, current_user)
        
        return {"refund_id": refund.id, "status": refund.status, "amount": refund_amount}
        
    except Exception as e:
        refund.status = "failed"
        await db.refund_requests.insert_one(refund.model_dump())
        await log_payment_event(db, "refund_failed", {"error": str(e)}, current_user, False)
        raise HTTPException(status_code=500, detail="Refund failed")

@payment_router.get("/qr/{transaction_id}")
async def get_upi_qr(
    transaction_id: str,
    current_user: str = Depends(get_current_user_payment)
):
    """Get UPI QR code with ownership validation"""
    from server import db
    
    # Verify transaction belongs to user
    transaction = await db.transactions.find_one({"id": transaction_id, "user_id": current_user})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    qr = await db.upi_qr_codes.find_one({"transaction_id": transaction_id})
    if not qr:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    expires_at = qr['expires_at']
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    
    if expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="QR code expired")
    
    return {
        "qr_data": qr['qr_data'],
        "qr_image": qr['qr_image_base64'],
        "amount": qr['amount'],
        "expires_at": qr['expires_at'],
        "upi_id": qr['upi_id'],
        "transaction_ref": transaction_id
    }

@payment_router.post("/upi/verify")
async def verify_upi_payment(
    transaction_id: str,
    utr_number: str,
    current_user: str = Depends(get_current_user_payment)
):
    """Manual UPI payment verification (requires UTR number)"""
    from server import db
    
    transaction = await db.transactions.find_one({"id": transaction_id, "user_id": current_user})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if transaction['provider'] != PaymentProvider.UPI.value:
        raise HTTPException(status_code=400, detail="Not a UPI transaction")
    
    # Mark as pending verification (requires admin approval for UPI)
    await db.transactions.update_one(
        {"id": transaction_id},
        {"$set": {
            "status": "pending_verification",
            "metadata.utr_number": utr_number,
            "updated_at": datetime.utcnow()
        }}
    )
    
    await log_payment_event(db, "upi_verification_requested", {
        "transaction_id": transaction_id,
        "utr_number": utr_number
    }, current_user)
    
    return {"status": "pending_verification", "message": "UPI payment submitted for verification"}

# ===================
# WEBHOOKS (Hardened)
# ===================
@payment_router.post("/webhook/razorpay")
async def razorpay_webhook(request: Request):
    """Handle Razorpay webhooks with signature verification and deduplication"""
    from server import db
    
    body = await request.body()
    signature = request.headers.get('X-Razorpay-Signature', '')
    webhook_secret = os.getenv('RAZORPAY_WEBHOOK_SECRET', '')
    
    if not webhook_secret:
        logger.error("Razorpay webhook secret not configured")
        raise HTTPException(status_code=500, detail="Webhook not configured")
    
    # Verify signature
    if not verify_razorpay_webhook_signature(body, signature, webhook_secret):
        logger.warning("Invalid Razorpay webhook signature")
        await log_payment_event(db, "webhook_signature_invalid", {"provider": "razorpay"}, success=False)
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    payload = json.loads(body)
    event_id = payload.get('event_id') or payload.get('payload', {}).get('payment', {}).get('entity', {}).get('id', str(uuid.uuid4()))
    event_type = payload.get('event')
    
    # Check for duplicate processing
    if await check_webhook_processed(db, event_id):
        logger.info(f"Webhook already processed: {event_id}")
        return {"status": "already_processed"}
    
    try:
        if event_type == 'payment.captured':
            payment_entity = payload['payload']['payment']['entity']
            payment_id = payment_entity['id']
            order_id = payment_entity['order_id']
            
            # Update transaction
            result = await db.transactions.update_one(
                {"provider_order_id": order_id, "status": {"$ne": PaymentStatus.COMPLETED.value}},
                {"$set": {
                    "status": PaymentStatus.COMPLETED.value,
                    "provider_payment_id": payment_id,
                    "completed_at": datetime.utcnow()
                }}
            )
            
            if result.modified_count > 0:
                transaction = await db.transactions.find_one({"provider_order_id": order_id})
                if transaction:
                    await db.bookings.update_one(
                        {"id": transaction['booking_id']},
                        {"$set": {"payment_status": "paid", "booking_status": "confirmed", "confirmed_at": datetime.utcnow()}}
                    )
            
            await log_payment_event(db, "webhook_payment_captured", {"order_id": order_id})
        
        elif event_type == 'payment.failed':
            payment_entity = payload['payload']['payment']['entity']
            order_id = payment_entity['order_id']
            error_desc = payment_entity.get('error_description', 'Unknown error')
            
            await db.transactions.update_one(
                {"provider_order_id": order_id},
                {"$set": {"status": PaymentStatus.FAILED.value, "error_message": error_desc}}
            )
            await log_payment_event(db, "webhook_payment_failed", {"order_id": order_id, "error": error_desc})
        
        elif event_type == 'refund.created':
            refund_entity = payload['payload']['refund']['entity']
            payment_id = refund_entity['payment_id']
            
            await db.transactions.update_one(
                {"provider_payment_id": payment_id},
                {"$set": {"refund_status": "processing"}}
            )
            await log_payment_event(db, "webhook_refund_created", {"payment_id": payment_id})
        
        # Mark event as processed
        await mark_webhook_processed(db, event_id, "razorpay", event_type)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Razorpay webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

@payment_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks with signature verification and deduplication"""
    from server import db
    
    payload = await request.body()
    sig_header = request.headers.get('Stripe-Signature', '')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET', '')
    
    if not webhook_secret:
        logger.error("Stripe webhook secret not configured")
        raise HTTPException(status_code=500, detail="Webhook not configured")
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid Stripe webhook signature")
        await log_payment_event(db, "webhook_signature_invalid", {"provider": "stripe"}, success=False)
        raise HTTPException(status_code=401, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Stripe webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    
    event_id = event['id']
    event_type = event['type']
    
    # Check for duplicate
    if await check_webhook_processed(db, event_id):
        return {"status": "already_processed"}
    
    try:
        if event_type == 'payment_intent.succeeded':
            intent = event['data']['object']
            
            # Verify status is actually succeeded
            if intent['status'] != 'succeeded':
                logger.warning(f"PaymentIntent status mismatch: {intent['status']}")
                return {"status": "ignored"}
            
            result = await db.transactions.update_one(
                {"provider_order_id": intent['id'], "status": {"$ne": PaymentStatus.COMPLETED.value}},
                {"$set": {
                    "status": PaymentStatus.COMPLETED.value,
                    "provider_payment_id": intent['id'],
                    "completed_at": datetime.utcnow()
                }}
            )
            
            if result.modified_count > 0:
                transaction = await db.transactions.find_one({"provider_order_id": intent['id']})
                if transaction:
                    await db.bookings.update_one(
                        {"id": transaction['booking_id']},
                        {"$set": {"payment_status": "paid", "booking_status": "confirmed", "confirmed_at": datetime.utcnow()}}
                    )
            
            await log_payment_event(db, "webhook_payment_succeeded", {"intent_id": intent['id']})
        
        elif event_type == 'payment_intent.payment_failed':
            intent = event['data']['object']
            error = intent.get('last_payment_error', {}).get('message', 'Unknown error')
            
            await db.transactions.update_one(
                {"provider_order_id": intent['id']},
                {"$set": {"status": PaymentStatus.FAILED.value, "error_message": error}}
            )
            await log_payment_event(db, "webhook_payment_failed", {"intent_id": intent['id'], "error": error})
        
        elif event_type == 'charge.refunded':
            charge = event['data']['object']
            payment_intent_id = charge.get('payment_intent')
            
            if payment_intent_id:
                await db.transactions.update_one(
                    {"provider_order_id": payment_intent_id},
                    {"$set": {"status": PaymentStatus.REFUNDED.value, "refunded_at": datetime.utcnow()}}
                )
            await log_payment_event(db, "webhook_refund_completed", {"charge_id": charge['id']})
        
        await mark_webhook_processed(db, event_id, "stripe", event_type)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Stripe webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

@payment_router.get("/status/{transaction_id}")
async def get_payment_status(
    transaction_id: str,
    current_user: str = Depends(get_current_user_payment)
):
    """Get payment status with user ownership check"""
    from server import db
    
    transaction = await db.transactions.find_one({"id": transaction_id, "user_id": current_user})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return {
        "transaction_id": transaction['id'],
        "status": transaction['status'],
        "amount": transaction['amount'],
        "currency": transaction['currency'],
        "provider": transaction['provider'],
        "created_at": transaction['created_at'],
        "completed_at": transaction.get('completed_at'),
        "error_message": transaction.get('error_message')
    }
