import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from decimal import Decimal

from FinSyncBilling.services import RazorpayService, BillingService
from FinSyncBilling.models import Payment, Invoice, BillingEvent, SubscriptionHistory
from FinSyncOrganizations.models import Organization

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    """Handle Razorpay webhook events"""
    try:
        # Get webhook data
        webhook_body = request.body.decode('utf-8')
        webhook_signature = request.headers.get('X-Razorpay-Signature', '')
        
        # Verify signature
        razorpay_service = RazorpayService()
        if not razorpay_service.verify_webhook_signature(webhook_body, webhook_signature):
            logger.error("Invalid webhook signature")
            return HttpResponse(status=400)
        
        # Parse webhook data
        webhook_data = json.loads(webhook_body)
        event_type = webhook_data.get('event')
        payload = webhook_data.get('payload', {})
        
        # Log webhook event
        BillingEvent.objects.create(
            organization=None,  # Will be updated by handler
            event_type="WEBHOOK_RECEIVED",
            description=f"Webhook received: {event_type}",
            metadata=webhook_data
        )
        
        # Route to appropriate handler
        handler_map = {
            'subscription.activated': handle_subscription_activated,
            'subscription.charged': handle_subscription_charged,
            'subscription.completed': handle_subscription_completed,
            'subscription.cancelled': handle_subscription_cancelled,
            'subscription.updated': handle_subscription_updated,
            'subscription.pending': handle_subscription_pending,
            'subscription.halted': handle_subscription_halted,
            'payment.failed': handle_payment_failed,
            'payment.captured': handle_payment_captured,
            'invoice.paid': handle_invoice_paid,
            'invoice.partially_paid': handle_invoice_partially_paid,
        }
        
        handler = handler_map.get(event_type)
        if handler:
            handler(payload)
            
            # Log successful processing
            BillingEvent.objects.create(
                organization=None,
                event_type="WEBHOOK_PROCESSED",
                description=f"Webhook processed successfully: {event_type}",
                metadata={"event": event_type}
            )
        else:
            logger.warning(f"Unhandled webhook event: {event_type}")
        
        return HttpResponse(status=200)
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        
        # Log failed processing
        BillingEvent.objects.create(
            organization=None,
            event_type="WEBHOOK_FAILED",
            description=f"Webhook processing failed: {str(e)}",
            metadata={"error": str(e), "body": request.body.decode('utf-8', errors='ignore')}
        )
        
        return HttpResponse(status=500)


def handle_subscription_activated(payload):
    """Handle subscription activation"""
    try:
        subscription = payload.get('subscription', {}).get('entity', {})
        subscription_id = subscription.get('id')
        
        # Find organization
        org = Organization.objects.filter(razorpay_subscription_id=subscription_id).first()
        if not org:
            logger.error(f"Organization not found for subscription: {subscription_id}")
            return
        
        with transaction.atomic():
            # Update organization status
            org.subscription_status = Organization.SubscriptionStatus.ACTIVE
            org.subscription_start_date = timezone.now().date()
            org.trial_ends_at = None  # Clear trial end date
            org.payment_failed_count = 0  # Reset failure count
            org.save()
            
            # Create history entry
            SubscriptionHistory.objects.create(
                organization=org,
                action="CREATED",
                to_plan=org.subscription_plan,
                razorpay_subscription_id=subscription_id,
                metadata={"subscription": subscription}
            )
            
            # Create billing event
            BillingEvent.objects.create(
                organization=org,
                event_type="SUBSCRIPTION_CREATED",
                description="Subscription activated successfully",
                metadata=payload
            )
            
    except Exception as e:
        logger.error(f"Error handling subscription activation: {str(e)}", exc_info=True)


def handle_subscription_charged(payload):
    """Handle successful subscription charge"""
    try:
        subscription = payload.get('subscription', {}).get('entity', {})
        payment = payload.get('payment', {}).get('entity', {})
        
        subscription_id = subscription.get('id')
        payment_id = payment.get('id')
        amount = Decimal(payment.get('amount', 0)) / 100  # Convert from paise
        
        # Find organization
        org = Organization.objects.filter(razorpay_subscription_id=subscription_id).first()
        if not org:
            logger.error(f"Organization not found for subscription: {subscription_id}")
            return
        
        with transaction.atomic():
            # Create payment record
            payment_record = Payment.objects.create(
                organization=org,
                razorpay_payment_id=payment_id,
                razorpay_order_id=payment.get('order_id'),
                amount=amount,
                currency=payment.get('currency', 'INR'),
                status='COMPLETED',
                payment_method=payment.get('method', 'CARD').upper(),
                paid_at=timezone.now(),
                metadata=payment
            )
            
            # Reset payment failure count
            org.payment_failed_count = 0
            org.last_payment_failed_at = None
            org.grace_period_ends_at = None
            org.save()
            
            # Generate invoice
            billing_service = BillingService()
            billing_service.generate_invoice(org, payment_record)
            
            # Create billing event
            BillingEvent.objects.create(
                organization=org,
                event_type="PAYMENT_COMPLETED",
                description=f"Payment of {amount} {payment.get('currency', 'INR')} received",
                payment=payment_record,
                metadata=payload
            )
            
            # TODO: Send payment success email
            
    except Exception as e:
        logger.error(f"Error handling subscription charge: {str(e)}", exc_info=True)


def handle_payment_failed(payload):
    """Handle failed payment"""
    try:
        payment = payload.get('payment', {}).get('entity', {})
        payment_id = payment.get('id')
        order_id = payment.get('order_id')
        error_description = payment.get('error_description', 'Unknown error')
        
        # Try to find organization by order metadata or existing payment
        org = None
        if order_id:
            # Check if we have a payment record with this order ID
            existing_payment = Payment.objects.filter(razorpay_order_id=order_id).first()
            if existing_payment:
                org = existing_payment.organization
        
        if not org:
            # Try to extract from notes
            notes = payment.get('notes', {})
            org_id = notes.get('organization_id')
            if org_id:
                org = Organization.objects.filter(id=org_id).first()
        
        if not org:
            logger.error(f"Organization not found for failed payment: {payment_id}")
            return
        
        with transaction.atomic():
            # Create payment record
            amount = Decimal(payment.get('amount', 0)) / 100
            payment_record = Payment.objects.create(
                organization=org,
                razorpay_payment_id=payment_id,
                razorpay_order_id=order_id,
                amount=amount,
                currency=payment.get('currency', 'INR'),
                status='FAILED',
                payment_method=payment.get('method', 'UNKNOWN').upper(),
                failure_reason=error_description,
                metadata=payment
            )
            
            # Update organization payment failure tracking
            org.payment_failed_count += 1
            org.last_payment_failed_at = timezone.now()
            
            # Set grace period if this is the first failure
            if org.payment_failed_count == 1:
                org.grace_period_ends_at = timezone.now() + timedelta(days=7)
            
            # Update subscription status if needed
            if org.payment_failed_count >= 1:
                org.subscription_status = Organization.SubscriptionStatus.PAST_DUE
            
            org.save()
            
            # Create billing event
            BillingEvent.objects.create(
                organization=org,
                event_type="PAYMENT_FAILED",
                description=f"Payment failed: {error_description}",
                payment=payment_record,
                metadata=payload
            )
            
            # TODO: Send payment failure email
            
    except Exception as e:
        logger.error(f"Error handling payment failure: {str(e)}", exc_info=True)


def handle_invoice_paid(payload):
    """Handle invoice payment"""
    try:
        invoice = payload.get('invoice', {}).get('entity', {})
        invoice_id = invoice.get('id')
        
        # Find existing invoice
        invoice_record = Invoice.objects.filter(razorpay_invoice_id=invoice_id).first()
        if invoice_record:
            invoice_record.status = 'PAID'
            invoice_record.paid_at = timezone.now()
            invoice_record.save()
            
            # Create billing event
            BillingEvent.objects.create(
                organization=invoice_record.organization,
                event_type="INVOICE_PAID",
                description=f"Invoice {invoice_record.invoice_number} paid",
                invoice=invoice_record,
                metadata=payload
            )
            
            # TODO: Send invoice email
            
    except Exception as e:
        logger.error(f"Error handling invoice payment: {str(e)}", exc_info=True)


def handle_invoice_partially_paid(payload):
    """Handle partial invoice payment"""
    try:
        invoice = payload.get('invoice', {}).get('entity', {})
        invoice_id = invoice.get('id')
        
        # Find existing invoice
        invoice_record = Invoice.objects.filter(razorpay_invoice_id=invoice_id).first()
        if invoice_record:
            invoice_record.status = 'PARTIALLY_PAID'
            invoice_record.save()
            
            # Create billing event
            BillingEvent.objects.create(
                organization=invoice_record.organization,
                event_type="INVOICE_PAID",
                description=f"Invoice {invoice_record.invoice_number} partially paid",
                invoice=invoice_record,
                metadata=payload
            )
            
    except Exception as e:
        logger.error(f"Error handling partial invoice payment: {str(e)}", exc_info=True)


def handle_subscription_completed(payload):
    """Handle subscription completion"""
    try:
        subscription = payload.get('subscription', {}).get('entity', {})
        subscription_id = subscription.get('id')
        
        org = Organization.objects.filter(razorpay_subscription_id=subscription_id).first()
        if org:
            org.subscription_status = Organization.SubscriptionStatus.CANCELED
            org.subscription_end_date = timezone.now().date()
            org.save()
            
            SubscriptionHistory.objects.create(
                organization=org,
                action="EXPIRED",
                from_plan=org.subscription_plan,
                razorpay_subscription_id=subscription_id,
                reason="Subscription completed",
                metadata={"subscription": subscription}
            )
            
            BillingEvent.objects.create(
                organization=org,
                event_type="SUBSCRIPTION_EXPIRED",
                description="Subscription completed/expired",
                metadata=payload
            )
            
    except Exception as e:
        logger.error(f"Error handling subscription completion: {str(e)}", exc_info=True)


def handle_subscription_cancelled(payload):
    """Handle subscription cancellation"""
    try:
        subscription = payload.get('subscription', {}).get('entity', {})
        subscription_id = subscription.get('id')
        
        org = Organization.objects.filter(razorpay_subscription_id=subscription_id).first()
        if org:
            org.subscription_status = Organization.SubscriptionStatus.CANCELED
            org.subscription_end_date = timezone.now().date()
            org.save()
            
            SubscriptionHistory.objects.create(
                organization=org,
                action="CANCELLED",
                from_plan=org.subscription_plan,
                razorpay_subscription_id=subscription_id,
                metadata={"subscription": subscription}
            )
            
            BillingEvent.objects.create(
                organization=org,
                event_type="SUBSCRIPTION_CANCELLED",
                description="Subscription cancelled",
                metadata=payload
            )
            
    except Exception as e:
        logger.error(f"Error handling subscription cancellation: {str(e)}", exc_info=True)


def handle_subscription_updated(payload):
    """Handle subscription update"""
    try:
        subscription = payload.get('subscription', {}).get('entity', {})
        subscription_id = subscription.get('id')
        
        org = Organization.objects.filter(razorpay_subscription_id=subscription_id).first()
        if org:
            BillingEvent.objects.create(
                organization=org,
                event_type="SUBSCRIPTION_UPDATED",
                description="Subscription updated",
                metadata=payload
            )
            
    except Exception as e:
        logger.error(f"Error handling subscription update: {str(e)}", exc_info=True)


def handle_subscription_pending(payload):
    """Handle subscription pending state"""
    try:
        subscription = payload.get('subscription', {}).get('entity', {})
        subscription_id = subscription.get('id')
        
        org = Organization.objects.filter(razorpay_subscription_id=subscription_id).first()
        if org:
            BillingEvent.objects.create(
                organization=org,
                event_type="SUBSCRIPTION_UPDATED",
                description="Subscription is pending",
                metadata=payload
            )
            
    except Exception as e:
        logger.error(f"Error handling subscription pending: {str(e)}", exc_info=True)


def handle_subscription_halted(payload):
    """Handle subscription halted state"""
    try:
        subscription = payload.get('subscription', {}).get('entity', {})
        subscription_id = subscription.get('id')
        
        org = Organization.objects.filter(razorpay_subscription_id=subscription_id).first()
        if org:
            org.subscription_status = Organization.SubscriptionStatus.PAST_DUE
            org.save()
            
            BillingEvent.objects.create(
                organization=org,
                event_type="SUBSCRIPTION_UPDATED",
                description="Subscription halted due to payment issues",
                metadata=payload
            )
            
    except Exception as e:
        logger.error(f"Error handling subscription halt: {str(e)}", exc_info=True)


def handle_payment_captured(payload):
    """Handle payment capture"""
    try:
        payment = payload.get('payment', {}).get('entity', {})
        payment_id = payment.get('id')
        
        # Update existing payment record
        payment_record = Payment.objects.filter(razorpay_payment_id=payment_id).first()
        if payment_record:
            payment_record.status = 'COMPLETED'
            payment_record.paid_at = timezone.now()
            payment_record.save()
            
            BillingEvent.objects.create(
                organization=payment_record.organization,
                event_type="PAYMENT_COMPLETED",
                description="Payment captured successfully",
                payment=payment_record,
                metadata=payload
            )
            
    except Exception as e:
        logger.error(f"Error handling payment capture: {str(e)}", exc_info=True)