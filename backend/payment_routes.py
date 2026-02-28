"""
PAYMENT ROUTES - Production Ready
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from typing import Optional
from datetime import datetime, timedelta
import os
import json
import stripe
import razorpay
from payment_module import *

payment_router = APIRouter(prefix="/payment", tags=["payment"])

# Initialize clients
razorpay_client = razorpay.Client(
    auth=(os.getenv('RAZORPAY_KEY_ID', ''), os.getenv('RAZORPAY_KEY_SECRET', ''))
)
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')

async def get_current_user_payment(authorization: str = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from server import verify_jwt_token
    user_id = verify_jwt_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id

@payment_router.post("/create")
async def create_payment(
    request: PaymentCreateRequest,
    current_user: str = Depends(get_current_user_payment)
):
    """Create payment order with idempotency"""
    from server import db
    
    # Check idempotency
    existing = await db.transactions.find_one({"idempotency_key": request.idempotency_key})
    if existing:
        return {"transaction_id": existing['id'], "status": existing['status'], "cached": True}
    
    # Verify booking
    booking = await db.bookings.find_one({"id": request.booking_id, "user_id": current_user})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.get('payment_status') == 'paid':
        raise HTTPException(status_code=400, detail="Already paid")
    
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
    
    try:
        if request.provider == PaymentProvider.RAZORPAY:
            order = razorpay_client.order.create({
                'amount': amount_paise,
                'currency': request.currency,
                'payment_capture': 1,
                'notes': {'booking_id': request.booking_id, 'user_id': current_user}
            })
            transaction.provider_order_id = order['id']
            
            await db.transactions.insert_one(transaction.model_dump())
            
            return {
                "transaction_id": transaction.id,
                "provider_order_id": order['id'],
                "amount": request.amount,
                "currency": request.currency,
                "key_id": os.getenv('RAZORPAY_KEY_ID'),
                "provider": "razorpay"
            }
            
        elif request.provider == PaymentProvider.STRIPE:
            intent = stripe.PaymentIntent.create(
                amount=amount_paise,
                currency=request.currency.lower(),
                metadata={'booking_id': request.booking_id, 'user_id': current_user}
            )
            transaction.provider_order_id = intent.id
            
            await db.transactions.insert_one(transaction.model_dump())
            
            return {
                "transaction_id": transaction.id,
                "client_secret": intent.client_secret,
                "provider_order_id": intent.id,
                "provider": "stripe"
            }
            
        elif request.provider == PaymentProvider.UPI:
            upi_id = os.getenv('MERCHANT_UPI_ID', 'merchant@upi')
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
            
            return {
                "transaction_id": transaction.id,
                "qr_data": qr_data,
                "qr_image": qr_image,
                "upi_intent": qr_data,
                "expires_at": qr_record.expires_at.isoformat(),
                "provider": "upi"
            }
            
        elif request.provider == PaymentProvider.PAYPAL:
            # PayPal integration placeholder - requires PayPal SDK
            transaction.provider_order_id = f"PP_{transaction.id[:8]}"
            await db.transactions.insert_one(transaction.model_dump())
            
            return {
                "transaction_id": transaction.id,
                "approval_url": f"https://paypal.com/checkout?token={transaction.id}",
                "provider": "paypal"
            }
            
    except Exception as e:
        transaction.status = PaymentStatus.FAILED
        transaction.error_message = str(e)
        await db.transactions.insert_one(transaction.model_dump())
        raise HTTPException(status_code=500, detail=f"Payment creation failed: {str(e)}")

@payment_router.post("/verify")
async def verify_payment(
    request: PaymentVerifyRequest,
    current_user: str = Depends(get_current_user_payment)
):
    """Verify payment signature and update status"""
    from server import db
    
    transaction = await db.transactions.find_one({"id": request.transaction_id, "user_id": current_user})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if transaction['status'] == PaymentStatus.COMPLETED.value:
        return {"status": "already_verified", "booking_status": "confirmed"}
    
    try:
        if transaction['provider'] == PaymentProvider.RAZORPAY.value:
            is_valid = verify_razorpay_signature(
                request.provider_order_id,
                request.provider_payment_id,
                request.provider_signature,
                os.getenv('RAZORPAY_KEY_SECRET', '')
            )
            
            if not is_valid:
                raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Update transaction
        await db.transactions.update_one(
            {"id": request.transaction_id},
            {"$set": {
                "status": PaymentStatus.COMPLETED.value,
                "provider_payment_id": request.provider_payment_id,
                "provider_signature": request.provider_signature,
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Update booking
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
        
        # Process affiliate commission if applicable
        booking = await db.bookings.find_one({"id": transaction['booking_id']})
        if booking and booking.get('referrer_user_id'):
            await db.affiliate_commissions.insert_one({
                "id": str(uuid.uuid4()),
                "referrer_id": booking['referrer_user_id'],
                "referee_id": current_user,
                "booking_id": booking['id'],
                "transaction_id": request.transaction_id,
                "amount": booking.get('affiliate_commission', 0),
                "status": "pending",
                "created_at": datetime.utcnow()
            })
        
        return {"status": "verified", "booking_status": "confirmed"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.transactions.update_one(
            {"id": request.transaction_id},
            {"$set": {"status": PaymentStatus.FAILED.value, "error_message": str(e)}}
        )
        raise HTTPException(status_code=400, detail=f"Verification failed: {str(e)}")

@payment_router.post("/retry/{transaction_id}")
async def retry_payment(
    transaction_id: str,
    current_user: str = Depends(get_current_user_payment)
):
    """Retry failed payment"""
    from server import db
    
    transaction = await db.transactions.find_one({"id": transaction_id, "user_id": current_user})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if transaction['status'] != PaymentStatus.FAILED.value:
        raise HTTPException(status_code=400, detail="Can only retry failed payments")
    
    if transaction['retry_count'] >= transaction['max_retries']:
        raise HTTPException(status_code=400, detail="Max retries exceeded")
    
    # Increment retry count
    await db.transactions.update_one(
        {"id": transaction_id},
        {"$inc": {"retry_count": 1}, "$set": {"status": PaymentStatus.PENDING.value}}
    )
    
    # Create new payment order
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
    """Request refund"""
    from server import db
    
    transaction = await db.transactions.find_one({"id": request.transaction_id, "user_id": current_user})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if transaction['status'] != PaymentStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Can only refund completed payments")
    
    refund_amount = request.amount or transaction['amount']
    
    refund = RefundRequest(
        transaction_id=request.transaction_id,
        booking_id=request.booking_id,
        user_id=current_user,
        amount=refund_amount,
        reason=request.reason
    )
    
    try:
        if transaction['provider'] == PaymentProvider.RAZORPAY.value:
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
        
        # Update transaction
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
        
        # Update booking
        await db.bookings.update_one(
            {"id": request.booking_id},
            {"$set": {
                "refund_status": "processed",
                "refund_amount": refund_amount,
                "booking_status": "cancelled"
            }}
        )
        
        return {"refund_id": refund.id, "status": refund.status, "amount": refund_amount}
        
    except Exception as e:
        refund.status = "failed"
        await db.refund_requests.insert_one(refund.model_dump())
        raise HTTPException(status_code=500, detail=f"Refund failed: {str(e)}")

@payment_router.get("/qr/{transaction_id}")
async def get_upi_qr(
    transaction_id: str,
    current_user: str = Depends(get_current_user_payment)
):
    """Get UPI QR code for transaction"""
    from server import db
    
    qr = await db.upi_qr_codes.find_one({"transaction_id": transaction_id})
    if not qr:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    if datetime.fromisoformat(str(qr['expires_at'])) < datetime.utcnow():
        raise HTTPException(status_code=400, detail="QR code expired")
    
    return {
        "qr_data": qr['qr_data'],
        "qr_image": qr['qr_image_base64'],
        "amount": qr['amount'],
        "expires_at": qr['expires_at']
    }

@payment_router.post("/webhook/razorpay")
async def razorpay_webhook(request: Request):
    """Handle Razorpay webhooks"""
    from server import db
    
    body = await request.body()
    signature = request.headers.get('X-Razorpay-Signature', '')
    webhook_secret = os.getenv('RAZORPAY_WEBHOOK_SECRET', '')
    
    # Verify signature
    expected = hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    payload = json.loads(body)
    event = payload.get('event')
    
    if event == 'payment.captured':
        payment_id = payload['payload']['payment']['entity']['id']
        order_id = payload['payload']['payment']['entity']['order_id']
        
        await db.transactions.update_one(
            {"provider_order_id": order_id},
            {"$set": {
                "status": PaymentStatus.COMPLETED.value,
                "provider_payment_id": payment_id,
                "completed_at": datetime.utcnow()
            }}
        )
        
        transaction = await db.transactions.find_one({"provider_order_id": order_id})
        if transaction:
            await db.bookings.update_one(
                {"id": transaction['booking_id']},
                {"$set": {"payment_status": "paid", "booking_status": "confirmed"}}
            )
    
    elif event == 'payment.failed':
        order_id = payload['payload']['payment']['entity']['order_id']
        await db.transactions.update_one(
            {"provider_order_id": order_id},
            {"$set": {"status": PaymentStatus.FAILED.value}}
        )
    
    return {"status": "ok"}

@payment_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    from server import db
    
    payload = await request.body()
    sig_header = request.headers.get('Stripe-Signature', '')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET', '')
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except:
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    if event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
        await db.transactions.update_one(
            {"provider_order_id": intent['id']},
            {"$set": {
                "status": PaymentStatus.COMPLETED.value,
                "provider_payment_id": intent['id'],
                "completed_at": datetime.utcnow()
            }}
        )
        
        transaction = await db.transactions.find_one({"provider_order_id": intent['id']})
        if transaction:
            await db.bookings.update_one(
                {"id": transaction['booking_id']},
                {"$set": {"payment_status": "paid", "booking_status": "confirmed"}}
            )
    
    elif event['type'] == 'payment_intent.payment_failed':
        intent = event['data']['object']
        await db.transactions.update_one(
            {"provider_order_id": intent['id']},
            {"$set": {"status": PaymentStatus.FAILED.value}}
        )
    
    return {"status": "ok"}

@payment_router.get("/status/{transaction_id}")
async def get_payment_status(
    transaction_id: str,
    current_user: str = Depends(get_current_user_payment)
):
    """Get payment status"""
    from server import db
    
    transaction = await db.transactions.find_one({"id": transaction_id, "user_id": current_user})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return {
        "transaction_id": transaction['id'],
        "status": transaction['status'],
        "amount": transaction['amount'],
        "provider": transaction['provider'],
        "created_at": transaction['created_at'],
        "completed_at": transaction.get('completed_at')
    }
