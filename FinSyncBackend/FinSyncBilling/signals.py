from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
import logging

from FinSyncOrganizations.models import Organization
from FinSyncBilling.models import BillingEvent

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Organization)
def check_plan_limits(sender, instance, **kwargs):
    """Check if organization is within plan limits before saving"""
    if instance.pk:  # Only for existing organizations
        try:
            old_instance = Organization.objects.get(pk=instance.pk)
            
            # Check if users are being added
            if hasattr(instance, '_adding_user') and instance._adding_user:
                if not instance.can_add_user():
                    from django.core.exceptions import ValidationError
                    raise ValidationError(
                        f"Cannot add user. Organization has reached the limit of {instance.subscription_plan.max_users} users for the {instance.subscription_plan.display_name} plan."
                    )
            
            # Check if subscription status changed
            if old_instance.subscription_status != instance.subscription_status:
                BillingEvent.objects.create(
                    organization=instance,
                    event_type="SUBSCRIPTION_UPDATED",
                    description=f"Subscription status changed from {old_instance.subscription_status} to {instance.subscription_status}"
                )
        except Organization.DoesNotExist:
            pass


@receiver(post_save, sender=Organization)
def create_trial_started_event(sender, instance, created, **kwargs):
    """Create a trial started event for new organizations"""
    if created and instance.subscription_status == Organization.SubscriptionStatus.TRIALING:
        BillingEvent.objects.create(
            organization=instance,
            event_type="TRIAL_STARTED",
            description=f"Trial started for {instance.trial_duration_days if hasattr(instance, 'trial_duration_days') else 14} days",
            user=instance.owner
        )