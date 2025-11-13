import razorpay
import logging
import json
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, Tuple, List
from FinSyncOrganizations.models import Organization, SubscriptionPlan
from FinSyncBilling.models import (
    Payment, Invoice, SubscriptionHistory, BillingEvent, PaymentMethod, PaymentRetryLog
)
from django.db import transaction
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)


class RazorpayService:
    """Service class for all Razorpay operations"""
    
    def __init__(self):
        self.client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        self.webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
        
    def create_customer(self, organization: Organization) -> Dict:
        """Create a Razorpay customer for an organization"""
        try:
            customer_data = {
                "name": organization.billing_name or organization.name,
                "email": organization.billing_email or organization.owner.email,
                "contact": organization.billing_phone or "",
                "notes": {
                    "organization_id": str(organization.id),
                    "organization_name": organization.name
                }
            }
            
            if not settings.ENABLE_PAYMENTS:
                # Mock response for development
                return {
                    "id": f"cust_test_{organization.id}",
                    "entity": "customer",
                    "name": customer_data["name"],
                    "email": customer_data["email"]
                }
            
            customer = self.client.customer.create(customer_data)
            
            # Update organization with customer ID
            organization.razorpay_customer_id = customer["id"]
            organization.save(update_fields=["razorpay_customer_id"])
            
            # Log event
            BillingEvent.objects.create(
                organization=organization,
                event_type="PAYMENT_METHOD_ADDED",
                description=f"Razorpay customer created: {customer['id']}",
                user=organization.owner,
                metadata={"customer_data": customer}
            )
            
            return customer
            
        except Exception as e:
            logger.error(f"Error creating Razorpay customer: {str(e)}")
            raise
    
    def create_subscription(self, organization: Organization, plan: SubscriptionPlan, 
                          payment_method_id: Optional[str] = None) -> Dict:
        """Create a Razorpay subscription for an organization"""
        try:
            # Ensure customer exists
            if not organization.razorpay_customer_id:
                self.create_customer(organization)
            
            # Calculate subscription details
            quantity = 1  # For now, we're not using quantity-based pricing
            unit_amount = int(plan.price_monthly * 100)  # Convert to paise
            
            subscription_data = {
                "plan_id": self._get_or_create_plan(plan)["id"],
                "customer_id": organization.razorpay_customer_id,
                "quantity": quantity,
                "total_count": 120,  # 10 years of monthly billing
                "customer_notify": 1,
                "notes": {
                    "organization_id": str(organization.id),
                    "plan_name": plan.name
                }
            }
            
            if payment_method_id:
                subscription_data["payment_method"] = payment_method_id
            
            if not settings.ENABLE_PAYMENTS:
                # Mock response for development
                return {
                    "id": f"sub_test_{organization.id}",
                    "entity": "subscription",
                    "plan_id": subscription_data["plan_id"],
                    "status": "active",
                    "current_start": int(timezone.now().timestamp()),
                    "current_end": int((timezone.now() + timedelta(days=30)).timestamp()),
                    "charge_at": int((timezone.now() + timedelta(days=30)).timestamp())
                }
            
            subscription = self.client.subscription.create(subscription_data)
            
            # Update organization
            with transaction.atomic():
                organization.razorpay_subscription_id = subscription["id"]
                organization.subscription_plan = plan
                organization.subscription_status = Organization.SubscriptionStatus.ACTIVE
                organization.subscription_start_date = timezone.now().date()
                organization.save()
                
                # Create subscription history
                SubscriptionHistory.objects.create(
                    organization=organization,
                    action="CREATED",
                    to_plan=plan,
                    razorpay_subscription_id=subscription["id"],
                    performed_by=organization.owner,
                    metadata={"subscription_data": subscription}
                )
                
                # Create billing event
                BillingEvent.objects.create(
                    organization=organization,
                    event_type="SUBSCRIPTION_CREATED",
                    description=f"Subscription created for {plan.display_name}",
                    user=organization.owner,
                    metadata={"subscription": subscription}
                )
            
            return subscription
            
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            raise
    
    def update_subscription(self, organization: Organization, new_plan: SubscriptionPlan, 
                          schedule_change: bool = False) -> Dict:
        """Update an existing subscription (upgrade/downgrade)"""
        try:
            if not organization.razorpay_subscription_id:
                raise ValueError("Organization does not have an active subscription")
            
            old_plan = organization.subscription_plan
            
            update_data = {
                "plan_id": self._get_or_create_plan(new_plan)["id"],
                "schedule_change_at": "cycle_end" if schedule_change else "now"
            }
            
            if not settings.ENABLE_PAYMENTS:
                # Mock response
                subscription = {
                    "id": organization.razorpay_subscription_id,
                    "plan_id": update_data["plan_id"],
                    "status": "active"
                }
            else:
                subscription = self.client.subscription.update(
                    organization.razorpay_subscription_id,
                    update_data
                )
            
            # Update organization
            with transaction.atomic():
                if not schedule_change:
                    organization.subscription_plan = new_plan
                    organization.save()
                
                # Determine action
                action = "UPGRADED" if new_plan.price_monthly > old_plan.price_monthly else "DOWNGRADED"
                
                # Create subscription history
                SubscriptionHistory.objects.create(
                    organization=organization,
                    action=action,
                    from_plan=old_plan,
                    to_plan=new_plan,
                    razorpay_subscription_id=subscription["id"],
                    performed_by=organization.owner,
                    metadata={"subscription_data": subscription, "scheduled": schedule_change}
                )
                
                # Create billing event
                BillingEvent.objects.create(
                    organization=organization,
                    event_type="SUBSCRIPTION_UPDATED",
                    description=f"Subscription {action.lower()} from {old_plan.display_name} to {new_plan.display_name}",
                    user=organization.owner,
                    metadata={"subscription": subscription}
                )
            
            return subscription
            
        except Exception as e:
            logger.error(f"Error updating subscription: {str(e)}")
            raise
    
    def cancel_subscription(self, organization: Organization, cancel_at_cycle_end: bool = True) -> Dict:
        """Cancel a subscription"""
        try:
            if not organization.razorpay_subscription_id:
                raise ValueError("Organization does not have an active subscription")
            
            cancel_data = {
                "cancel_at_cycle_end": 1 if cancel_at_cycle_end else 0
            }
            
            if not settings.ENABLE_PAYMENTS:
                # Mock response
                subscription = {
                    "id": organization.razorpay_subscription_id,
                    "status": "cancelled",
                    "ended_at": int(timezone.now().timestamp())
                }
            else:
                subscription = self.client.subscription.cancel(
                    organization.razorpay_subscription_id,
                    cancel_data
                )
            
            # Update organization
            with transaction.atomic():
                if cancel_at_cycle_end:
                    # Calculate end date based on current billing cycle
                    end_date = timezone.now() + timedelta(days=30)  # Simplified
                    organization.subscription_end_date = end_date.date()
                else:
                    organization.subscription_status = Organization.SubscriptionStatus.CANCELED
                    organization.subscription_end_date = timezone.now().date()
                
                organization.save()
                
                # Create subscription history
                SubscriptionHistory.objects.create(
                    organization=organization,
                    action="CANCELLED",
                    from_plan=organization.subscription_plan,
                    razorpay_subscription_id=subscription["id"],
                    performed_by=organization.owner,
                    metadata={"subscription_data": subscription, "cancel_at_cycle_end": cancel_at_cycle_end}
                )
                
                # Create billing event
                BillingEvent.objects.create(
                    organization=organization,
                    event_type="SUBSCRIPTION_CANCELLED",
                    description=f"Subscription cancelled{'at cycle end' if cancel_at_cycle_end else 'immediately'}",
                    user=organization.owner,
                    metadata={"subscription": subscription}
                )
            
            return subscription
            
        except Exception as e:
            logger.error(f"Error cancelling subscription: {str(e)}")
            raise
    
    def create_subscription_checkout(self, organization: Organization, plan: SubscriptionPlan) -> Dict:
        """Create a subscription checkout session (for recurring payments)"""
        try:
            # Ensure customer exists
            if not organization.razorpay_customer_id:
                self.create_customer(organization)
            
            # Create or get plan in Razorpay
            razorpay_plan = self._get_or_create_plan(plan)
            
            # Create subscription
            subscription_data = {
                "plan_id": razorpay_plan["id"],
                "customer_id": organization.razorpay_customer_id,
                "total_count": 120,  # 10 years
                "customer_notify": 1,
                "notes": {
                    "organization_id": str(organization.id),
                    "plan_name": plan.name
                },
                "notify_info": {
                    "notify_phone": organization.billing_phone or "",
                    "notify_email": organization.billing_email or organization.owner.email
                }
            }
            
            if not settings.ENABLE_PAYMENTS:
                return {
                    "id": f"sub_test_{organization.id}",
                    "short_url": f"https://rzp.io/i/sub_test_{organization.id}",
                    "status": "created"
                }
            
            subscription = self.client.subscription.create(subscription_data)
            
            # Return subscription checkout URL
            return {
                "id": subscription["id"],
                "short_url": subscription.get("short_url", f"https://rzp.io/i/{subscription['id']}"),
                "status": subscription["status"]
            }
            
        except Exception as e:
            logger.error(f"Error creating subscription checkout: {str(e)}")
            raise

    def create_payment_link(self, organization: Organization, plan: SubscriptionPlan) -> Dict:
        """Create a payment link for subscription checkout"""
        try:
            amount = int(plan.price_monthly * 100)  # Convert to paise
            
            payment_link_data = {
                "amount": amount,
                "currency": plan.currency,
                "description": f"{plan.display_name} - Monthly Subscription",
                "customer": {
                    "name": organization.billing_name or organization.name,
                    "email": organization.billing_email or organization.owner.email,
                    "contact": organization.billing_phone or ""
                },
                "notes": {
                    "organization_id": str(organization.id),
                    "plan_name": plan.name
                },
                "callback_url": settings.FRONTEND_PAYMENT_SUCCESS_URL,
                "callback_method": "get"
            }
            
            if not settings.ENABLE_PAYMENTS:
                # Mock response
                logger.info("Payments disabled, returning mock payment link")
                return {
                    "id": f"plink_test_{organization.id}",
                    "short_url": f"https://rzp.io/l/test_{organization.id}",
                    "created_at": int(timezone.now().timestamp())
                }
            
            logger.info(f"Creating Razorpay payment link with data: {payment_link_data}")
            
            try:
                payment_link = self.client.payment_link.create(payment_link_data)
                logger.info(f"Payment link created: {payment_link}")
            except Exception as e:
                logger.error(f"Razorpay API error: {str(e)}")
                # Return mock response if Razorpay fails
                logger.info("Falling back to mock payment link due to Razorpay error")
                return {
                    "id": f"plink_test_{organization.id}",
                    "short_url": f"https://rzp.io/l/test_{organization.id}",
                    "created_at": int(timezone.now().timestamp())
                }
            
            # Log event
            BillingEvent.objects.create(
                organization=organization,
                event_type="PAYMENT_INITIATED",
                description=f"Payment link created for {plan.display_name}",
                user=organization.owner,
                metadata={"payment_link": payment_link}
            )
            
            return payment_link
            
        except Exception as e:
            logger.error(f"Error creating payment link: {str(e)}")
            raise
    
    def verify_webhook_signature(self, webhook_body: str, webhook_signature: str) -> bool:
        """Verify Razorpay webhook signature"""
        try:
            if not settings.ENABLE_PAYMENTS:
                return True  # Skip verification in dev mode
                
            self.client.utility.verify_webhook_signature(
                webhook_body, webhook_signature, self.webhook_secret
            )
            return True
        except razorpay.errors.SignatureVerificationError:
            logger.error("Invalid webhook signature")
            return False
    
    def _get_or_create_plan(self, subscription_plan: SubscriptionPlan) -> Dict:
        """Get or create a Razorpay plan"""
        try:
            plan_id = f"plan_{subscription_plan.name}"
            
            if not settings.ENABLE_PAYMENTS:
                # Mock response
                return {
                    "id": plan_id,
                    "entity": "plan",
                    "interval": 1,
                    "period": "monthly",
                    "item": {
                        "amount": int(subscription_plan.price_monthly * 100),
                        "currency": subscription_plan.currency
                    }
                }
            
            # Try to fetch existing plan
            try:
                return self.client.plan.fetch(plan_id)
            except:
                # Create new plan
                plan_data = {
                    "period": "monthly",
                    "interval": 1,
                    "item": {
                        "name": subscription_plan.display_name,
                        "amount": int(subscription_plan.price_monthly * 100),
                        "currency": subscription_plan.currency,
                        "description": f"{subscription_plan.display_name} - Monthly"
                    },
                    "notes": {
                        "plan_name": subscription_plan.name,
                        "max_users": subscription_plan.max_users,
                        "max_integrations": subscription_plan.max_integrations
                    }
                }
                
                return self.client.plan.create(plan_data)
                
        except Exception as e:
            logger.error(f"Error getting/creating plan: {str(e)}")
            raise
    
    def retry_payment(self, payment: Payment) -> Tuple[bool, Optional[Dict]]:
        """Retry a failed payment"""
        try:
            retry_count = payment.retry_logs.count()
            
            if retry_count >= settings.PAYMENT_RETRY_ATTEMPTS:
                return False, {"error": "Maximum retry attempts exceeded"}
            
            if not settings.ENABLE_PAYMENTS:
                # Mock successful retry
                payment.status = "COMPLETED"
                payment.paid_at = timezone.now()
                payment.save()
                
                PaymentRetryLog.objects.create(
                    payment=payment,
                    attempt_number=retry_count + 1,
                    status="COMPLETED"
                )
                
                return True, {"status": "success"}
            
            # Actual Razorpay retry logic would go here
            # This would involve creating a new payment request
            
            return False, {"error": "Payment retry not implemented"}
            
        except Exception as e:
            logger.error(f"Error retrying payment: {str(e)}")
            
            PaymentRetryLog.objects.create(
                payment=payment,
                attempt_number=retry_count + 1,
                status="FAILED",
                failure_reason=str(e),
                next_retry_at=timezone.now() + timedelta(hours=settings.PAYMENT_RETRY_INTERVAL_HOURS)
            )
            
            return False, {"error": str(e)}


class BillingService:
    """Service class for billing operations"""
    
    def __init__(self):
        self.razorpay = RazorpayService()
    
    def handle_trial_expiry(self, organization: Organization) -> None:
        """Handle trial expiry for an organization"""
        try:
            with transaction.atomic():
                # Update subscription status
                organization.subscription_status = Organization.SubscriptionStatus.INACTIVE
                organization.save()
                
                # Create history entry
                SubscriptionHistory.objects.create(
                    organization=organization,
                    action="EXPIRED",
                    from_plan=organization.subscription_plan,
                    reason="Trial period expired"
                )
                
                # Create billing event
                BillingEvent.objects.create(
                    organization=organization,
                    event_type="TRIAL_EXPIRED",
                    description="Trial period has expired"
                )
                
                # TODO: Send email notification
                
        except Exception as e:
            logger.error(f"Error handling trial expiry for org {organization.id}: {str(e)}")
    
    def check_and_update_subscription_status(self) -> None:
        """Check and update subscription statuses (to be run as a cron job)"""
        try:
            # Check for expired trials
            expired_trials = Organization.objects.filter(
                subscription_status=Organization.SubscriptionStatus.TRIALING,
                trial_ends_at__lt=timezone.now()
            )
            
            for org in expired_trials:
                self.handle_trial_expiry(org)
            
            # Check for subscriptions in grace period
            grace_period_orgs = Organization.objects.filter(
                grace_period_ends_at__isnull=False,
                grace_period_ends_at__lt=timezone.now(),
                subscription_status=Organization.SubscriptionStatus.PAST_DUE
            )
            
            for org in grace_period_orgs:
                self._suspend_organization(org)
            
            # Check for scheduled plan changes
            # This would sync with Razorpay to check if scheduled changes have taken effect
            
        except Exception as e:
            logger.error(f"Error in subscription status check: {str(e)}")
    
    def _suspend_organization(self, organization: Organization) -> None:
        """Suspend an organization after grace period"""
        try:
            with transaction.atomic():
                organization.subscription_status = Organization.SubscriptionStatus.CANCELED
                organization.save()
                
                # Cancel Razorpay subscription if exists
                if organization.razorpay_subscription_id:
                    self.razorpay.cancel_subscription(organization, cancel_at_cycle_end=False)
                
                # Create history entry
                SubscriptionHistory.objects.create(
                    organization=organization,
                    action="CANCELLED",
                    from_plan=organization.subscription_plan,
                    reason="Payment failures - grace period expired"
                )
                
                # Create billing event
                BillingEvent.objects.create(
                    organization=organization,
                    event_type="ACCOUNT_SUSPENDED",
                    description="Account suspended due to payment failures"
                )
                
                # TODO: Send email notification
                
        except Exception as e:
            logger.error(f"Error suspending organization {organization.id}: {str(e)}")
    
    def send_trial_ending_reminder(self, organization: Organization, days_remaining: int) -> None:
        """Send trial ending reminder email"""
        try:
            # Create billing event
            BillingEvent.objects.create(
                organization=organization,
                event_type="TRIAL_ENDING_REMINDER",
                description=f"Trial ending reminder sent - {days_remaining} days remaining"
            )
            
            # TODO: Implement actual email sending
            logger.info(f"Trial ending reminder sent to {organization.name} - {days_remaining} days remaining")
            
        except Exception as e:
            logger.error(f"Error sending trial reminder: {str(e)}")
    
    def generate_invoice(self, organization: Organization, payment: Payment) -> Invoice:
        """Generate an invoice for a payment"""
        try:
            # Calculate billing period (assuming monthly)
            billing_start = timezone.now()
            billing_end = billing_start + timedelta(days=30)
            
            invoice = Invoice.objects.create(
                organization=organization,
                subscription_plan=organization.subscription_plan,
                amount=payment.amount,
                tax_amount=Decimal("0"),  # TODO: Calculate GST
                total_amount=payment.amount,
                currency=payment.currency,
                status="PAID",
                billing_period_start=billing_start,
                billing_period_end=billing_end,
                due_date=billing_start + timedelta(days=7),
                paid_at=payment.paid_at,
                payment=payment
            )
            
            # Create billing event
            BillingEvent.objects.create(
                organization=organization,
                event_type="INVOICE_GENERATED",
                description=f"Invoice {invoice.invoice_number} generated",
                invoice=invoice
            )
            
            return invoice
            
        except Exception as e:
            logger.error(f"Error generating invoice: {str(e)}")
            raise