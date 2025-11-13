from django.core.management.base import BaseCommand
from django.utils import timezone
from FinSyncBilling.models import Payment, Invoice, BillingEvent, SubscriptionHistory
from FinSyncBilling.services import RazorpayService
from FinSyncOrganizations.models import Organization, SubscriptionPlan
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manually verify payment status from Razorpay and update database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--payment-id',
            type=str,
            help='Razorpay payment ID to verify',
        )
        parser.add_argument(
            '--org-id',
            type=int,
            help='Organization ID to update',
        )
        parser.add_argument(
            '--mark-as-paid',
            action='store_true',
            help='Force mark as paid (for testing only)',
        )

    def handle(self, *args, **options):
        payment_id = options.get('payment-id')
        org_id = options.get('org_id')
        force_paid = options.get('mark_as_paid', False)

        if not org_id:
            self.stdout.write(self.style.ERROR('Organization ID is required'))
            return

        try:
            org = Organization.objects.get(id=org_id)
            self.stdout.write(f"Processing payment for organization: {org.name}")

            if force_paid:
                # Force update for testing
                self._mark_payment_successful(org)
                self.stdout.write(self.style.SUCCESS('Payment marked as successful (test mode)'))
            else:
                # Verify with Razorpay
                if not payment_id:
                    self.stdout.write(self.style.ERROR('Payment ID is required for verification'))
                    return
                
                razorpay_service = RazorpayService()
                try:
                    payment = razorpay_service.client.payment.fetch(payment_id)
                    
                    if payment['status'] == 'captured':
                        self._mark_payment_successful(org, payment_id, payment)
                        self.stdout.write(self.style.SUCCESS('Payment verified and marked as successful'))
                    else:
                        self.stdout.write(self.style.WARNING(f'Payment status: {payment["status"]}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error verifying payment: {str(e)}'))

        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Organization with ID {org_id} not found'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))

    def _mark_payment_successful(self, org, payment_id=None, payment_data=None):
        """Update all necessary records after successful payment"""
        
        # Get the plan (assuming individual plan for now)
        plan = SubscriptionPlan.objects.get(name='individual')
        
        # Create or update payment record
        payment_record = Payment.objects.create(
            organization=org,
            razorpay_payment_id=payment_id or f'test_payment_{org.id}',
            amount=plan.price_monthly,
            currency=plan.currency,
            status='COMPLETED',
            payment_method='CARD',
            description=f'Payment for {plan.display_name}',
            paid_at=timezone.now(),
            metadata=payment_data or {}
        )
        
        # Update organization subscription
        org.subscription_status = Organization.SubscriptionStatus.ACTIVE
        org.subscription_plan = plan
        org.subscription_start_date = timezone.now().date()
        org.trial_ends_at = None  # Clear trial end date
        # For test, create a fake subscription ID
        if not org.razorpay_subscription_id:
            org.razorpay_subscription_id = f'sub_test_{org.id}'
        org.save()
        
        # Create invoice
        invoice = Invoice.objects.create(
            organization=org,
            subscription_plan=plan,
            amount=plan.price_monthly,
            tax_amount=0,  # Simplified for testing
            total_amount=plan.price_monthly,
            currency=plan.currency,
            status='PAID',
            billing_period_start=timezone.now(),
            billing_period_end=timezone.now() + timezone.timedelta(days=30),
            due_date=timezone.now(),
            paid_at=timezone.now(),
            payment=payment_record
        )
        
        # Create subscription history
        SubscriptionHistory.objects.create(
            organization=org,
            action='CREATED',
            from_plan=None,
            to_plan=plan,
            performed_by=org.owner,
            metadata={'payment_id': payment_id}
        )
        
        # Create billing events
        BillingEvent.objects.create(
            organization=org,
            event_type='PAYMENT_COMPLETED',
            description=f'Payment completed for {plan.display_name}',
            payment=payment_record,
            invoice=invoice,
            user=org.owner
        )
        
        BillingEvent.objects.create(
            organization=org,
            event_type='SUBSCRIPTION_CREATED',
            description=f'Subscription activated: {plan.display_name}',
            user=org.owner
        )
        
        self.stdout.write(self.style.SUCCESS(f"""
        Updated records:
        - Payment: {payment_record.id}
        - Invoice: {invoice.invoice_number}
        - Organization status: {org.subscription_status}
        - Subscription plan: {org.subscription_plan.display_name}
        """))