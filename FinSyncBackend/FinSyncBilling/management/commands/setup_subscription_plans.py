from django.core.management.base import BaseCommand
from django.conf import settings
from decimal import Decimal
from FinSyncOrganizations.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Set up initial subscription plans with pricing'
    
    def handle(self, *args, **options):
        self.stdout.write("Setting up subscription plans...")
        
        # Update or create trial plan
        trial_plan, created = SubscriptionPlan.objects.update_or_create(
            name='trial',
            defaults={
                'display_name': 'Free Trial',
                'max_users': 1,
                'max_integrations': 1,
                'is_trial': True,
                'trial_duration_days': 14,
                'price_monthly': Decimal('0.00'),
                'currency': 'INR',
                'is_available': False,  # Not directly selectable
                'features': {
                    'support': 'Community support',
                    'api_access': False,
                    'data_export': False,
                    'analytics': False,
                }
            }
        )
        self.stdout.write(
            self.style.SUCCESS(f"{'Created' if created else 'Updated'} trial plan")
        )
        
        # Update or create individual plan
        individual_plan, created = SubscriptionPlan.objects.update_or_create(
            name='individual',
            defaults={
                'display_name': 'Individual Plan',
                'max_users': 1,
                'max_integrations': 3,
                'is_trial': False,
                'price_monthly': settings.SUBSCRIPTION_PRICING['individual']['monthly'],
                'currency': 'INR',
                'is_available': True,
                'features': {
                    'support': 'Email support',
                    'api_access': True,
                    'data_export': True,
                    'analytics': False,
                }
            }
        )
        self.stdout.write(
            self.style.SUCCESS(f"{'Created' if created else 'Updated'} individual plan")
        )
        
        # Update or create team plan
        team_plan, created = SubscriptionPlan.objects.update_or_create(
            name='team',
            defaults={
                'display_name': 'Team Plan',
                'max_users': 10,
                'max_integrations': 5,
                'is_trial': False,
                'price_monthly': settings.SUBSCRIPTION_PRICING['team']['monthly'],
                'currency': 'INR',
                'is_available': True,
                'features': {
                    'support': 'Priority email support',
                    'api_access': True,
                    'data_export': True,
                    'analytics': True,
                }
            }
        )
        self.stdout.write(
            self.style.SUCCESS(f"{'Created' if created else 'Updated'} team plan")
        )
        
        # Display summary
        self.stdout.write("\nSubscription Plans Summary:")
        for plan in SubscriptionPlan.objects.all():
            self.stdout.write(
                f"- {plan.display_name}: ₹{plan.price_monthly}/month "
                f"({plan.max_users} users, {plan.max_integrations} integrations)"
            )