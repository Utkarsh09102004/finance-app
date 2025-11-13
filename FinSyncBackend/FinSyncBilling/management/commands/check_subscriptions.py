from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

from FinSyncBilling.services import BillingService
from FinSyncOrganizations.models import Organization
from FinSyncBilling.models import Payment, PaymentRetryLog

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check and update subscription statuses'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making any changes'
        )
    
    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        billing_service = BillingService()
        
        self.stdout.write("Starting subscription status check...")
        
        # 1. Check for expired trials
        self.check_expired_trials(billing_service, dry_run)
        
        # 2. Check for trials ending soon (3 days and 1 day)
        self.check_trial_reminders(billing_service, dry_run)
        
        # 3. Check for failed payments that need retry
        self.check_payment_retries(billing_service, dry_run)
        
        # 4. Check for organizations in grace period
        self.check_grace_period_expiry(billing_service, dry_run)
        
        # 5. Update subscription statuses from Razorpay
        if not dry_run:
            billing_service.check_and_update_subscription_status()
        
        self.stdout.write(self.style.SUCCESS("Subscription status check completed"))
    
    def check_expired_trials(self, billing_service, dry_run):
        """Check for expired trials"""
        expired_trials = Organization.objects.filter(
            subscription_status=Organization.SubscriptionStatus.TRIALING,
            trial_ends_at__lt=timezone.now()
        )
        
        count = expired_trials.count()
        if count > 0:
            self.stdout.write(f"Found {count} expired trials")
            
            if not dry_run:
                for org in expired_trials:
                    try:
                        billing_service.handle_trial_expiry(org)
                        self.stdout.write(f"  - Handled trial expiry for: {org.name}")
                    except Exception as e:
                        self.stderr.write(f"  - Error handling trial expiry for {org.name}: {str(e)}")
    
    def check_trial_reminders(self, billing_service, dry_run):
        """Send trial ending reminders"""
        now = timezone.now()
        
        # 3-day reminder
        three_days_from_now = now + timedelta(days=3)
        orgs_3_days = Organization.objects.filter(
            subscription_status=Organization.SubscriptionStatus.TRIALING,
            trial_ends_at__date=three_days_from_now.date()
        ).exclude(
            billing_events__event_type='TRIAL_ENDING_REMINDER',
            billing_events__created_at__date=now.date()
        )
        
        if orgs_3_days.exists():
            self.stdout.write(f"Sending 3-day trial reminders to {orgs_3_days.count()} organizations")
            if not dry_run:
                for org in orgs_3_days:
                    billing_service.send_trial_ending_reminder(org, 3)
        
        # 1-day reminder
        one_day_from_now = now + timedelta(days=1)
        orgs_1_day = Organization.objects.filter(
            subscription_status=Organization.SubscriptionStatus.TRIALING,
            trial_ends_at__date=one_day_from_now.date()
        ).exclude(
            billing_events__event_type='TRIAL_ENDING_REMINDER',
            billing_events__created_at__date=now.date()
        )
        
        if orgs_1_day.exists():
            self.stdout.write(f"Sending 1-day trial reminders to {orgs_1_day.count()} organizations")
            if not dry_run:
                for org in orgs_1_day:
                    billing_service.send_trial_ending_reminder(org, 1)
    
    def check_payment_retries(self, billing_service, dry_run):
        """Check for payments that need retry"""
        # Get failed payments that haven't exceeded retry limit
        from django.conf import settings
        from django.db.models import Count
        
        failed_payments = Payment.objects.filter(
            status='FAILED',
            created_at__gte=timezone.now() - timedelta(days=30)  # Only recent failures
        ).annotate(
            retry_count=Count('retry_logs')
        ).filter(
            retry_count__lt=settings.PAYMENT_RETRY_ATTEMPTS
        )
        
        # Check if it's time for retry
        payments_to_retry = []
        for payment in failed_payments:
            last_retry = payment.retry_logs.order_by('-created_at').first()
            if last_retry:
                next_retry_time = last_retry.created_at + timedelta(hours=settings.PAYMENT_RETRY_INTERVAL_HOURS)
                if timezone.now() >= next_retry_time:
                    payments_to_retry.append(payment)
            else:
                # No retries yet, retry now
                payments_to_retry.append(payment)
        
        if payments_to_retry:
            self.stdout.write(f"Found {len(payments_to_retry)} payments to retry")
            if not dry_run:
                for payment in payments_to_retry:
                    try:
                        success, result = billing_service.razorpay.retry_payment(payment)
                        if success:
                            self.stdout.write(f"  - Successfully retried payment {payment.id}")
                        else:
                            self.stdout.write(f"  - Failed to retry payment {payment.id}: {result.get('error')}")
                    except Exception as e:
                        self.stderr.write(f"  - Error retrying payment {payment.id}: {str(e)}")
    
    def check_grace_period_expiry(self, billing_service, dry_run):
        """Check for organizations whose grace period has expired"""
        expired_grace_period = Organization.objects.filter(
            grace_period_ends_at__isnull=False,
            grace_period_ends_at__lt=timezone.now(),
            subscription_status=Organization.SubscriptionStatus.PAST_DUE
        )
        
        count = expired_grace_period.count()
        if count > 0:
            self.stdout.write(f"Found {count} organizations with expired grace period")
            
            if not dry_run:
                for org in expired_grace_period:
                    try:
                        billing_service._suspend_organization(org)
                        self.stdout.write(f"  - Suspended organization: {org.name}")
                    except Exception as e:
                        self.stderr.write(f"  - Error suspending {org.name}: {str(e)}")