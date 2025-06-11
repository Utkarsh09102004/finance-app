import logging
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

# Forward reference for type hinting
if False: # This block is never executed but allows type hinting
    from FinSyncOrganizations.models import SubscriptionPlan, Organization, OrganizationInvite
    from FinSyncAuth.models import CustomUser

def get_or_create_trial_plan():
    """
    Retrieves the default trial subscription plan or creates it if it doesn't exist.
    
    Returns:
        tuple: (SubscriptionPlan, created)
            - SubscriptionPlan: The trial plan object
            - created: Boolean indicating if the plan was created (True) or fetched (False)
    
    Raises:
        ValidationError: If creating a trial plan fails or if multiple trial plans exist
    """
    # Import here to avoid circular imports
    from FinSyncOrganizations.models import SubscriptionPlan
    
    try:
        # Try to get the existing trial plan
        trial_plan = SubscriptionPlan.objects.get(is_trial=True)
        return trial_plan, False
    except SubscriptionPlan.DoesNotExist:
        logger.info("Default trial plan not found. Creating one.")
        try:
            # Define sensible defaults for a new trial plan
            trial_plan = SubscriptionPlan.objects.create(
                name=SubscriptionPlan.PlanName.TRIAL,
                display_name="Trial Plan",
                max_users=getattr(settings, 'DEFAULT_TRIAL_MAX_USERS', 1),
                max_integrations=getattr(settings, 'DEFAULT_TRIAL_MAX_INTEGRATIONS', 1),
                is_trial=True,
                trial_duration_days=getattr(settings, 'DEFAULT_TRIAL_DURATION_DAYS', 14),
                is_available=False  # Not directly selectable by users
            )
            logger.info(f"Successfully created default trial plan: {trial_plan.name}")
            return trial_plan, True
        except Exception as e:
            logger.critical(f"FATAL: Could not create default trial plan: {e}", exc_info=True)
            raise ValidationError(f"Failed to create the default trial SubscriptionPlan. Error: {e}")
    except SubscriptionPlan.MultipleObjectsReturned:
        logger.critical("FATAL: Multiple default trial plans found. Ambiguous setup.")
        raise ValidationError("Multiple default trial SubscriptionPlans found. Database misconfiguration.")

def apply_trial_plan_to_organization(organization: 'Organization'):
    """
    Finds the default trial SubscriptionPlan and applies it to the given Organization.
    Sets trial_ends_at based on the plan's duration.
    Raises ValidationError if no trial plan is found or if the organization already has a plan.
    """
    # Import here to avoid circular imports at the module level
    from FinSyncOrganizations.models import SubscriptionPlan, Organization

    if organization.subscription_plan_id:
        # Should not happen if called correctly from Organization.save()
        logger.warning(f"Attempted to apply trial plan to organization '{organization.name}' which already has plan '{organization.subscription_plan_id}'.")
        return

    try:
        trial_plan = SubscriptionPlan.objects.get(is_trial=True)
    except SubscriptionPlan.DoesNotExist:
        logger.critical("CRITICAL: No SubscriptionPlan marked as is_trial=True exists in the database. Cannot assign trial plan.")
        raise ValidationError("Could not find a default trial subscription plan. Please contact support.")
    except SubscriptionPlan.MultipleObjectsReturned:
        logger.error("Multiple SubscriptionPlans found marked as is_trial=True. Using the first one found.")
        # Depending on policy, you might want to raise ValidationError here instead.
        trial_plan = SubscriptionPlan.objects.filter(is_trial=True).first()

    organization.subscription_plan = trial_plan
    organization.subscription_status = Organization.SubscriptionStatus.TRIALING

    if trial_plan.trial_duration_days:
        organization.trial_ends_at = timezone.now() + timedelta(days=trial_plan.trial_duration_days)
    else:
        # Fallback if trial duration isn't set on the plan (should be caught by Plan.clean)
        organization.trial_ends_at = timezone.now() + timedelta(days=14)
        logger.warning(f"Trial plan '{trial_plan.name}' missing trial_duration_days. Defaulting trial end date for org '{organization.name}'.")

    logger.info(f"Applied trial plan '{trial_plan.name}' to organization '{organization.name}'. Trial ends: {organization.trial_ends_at}")

def send_organization_invite_email(invite: 'OrganizationInvite'):
    """
    Sends an email to the invited user containing the invite code and org name.
    """
    if not invite.email:
        logger.warning(f"Invite {invite.id} has no email address. Skipping email notification.")
        return

    organization_name = invite.organization.name
    inviter_name = invite.created_by.get_full_name() or invite.created_by.email
    invite_code = invite.code
    # Consider adding an expiry message if invite.expires_at is set
    # TODO: Make frontend URL configurable via settings
    # accept_url = f"https://yourfrontend.com/accept-invite?code={invite_code}"

    subject = f"Invitation to join {organization_name} on FinSync"
    message = f"""Hi {invite.email},

You have been invited by {inviter_name} to join the organization '{organization_name}' on FinSync.

Use the following code to accept the invitation:
{invite_code}

Alternatively, click here to accept (if frontend handles this):
[Link to accept - requires frontend URL]

If you were not expecting this invitation, you can safely ignore this email.

Thanks,
The FinSync Team
"""
    from_email = settings.DEFAULT_FROM_EMAIL # Make sure this is set in settings.py
    recipient_list = [invite.email]

    try:
        send_mail(subject, message, from_email, recipient_list, fail_silently=False)
        logger.info(f"Sent invite email for invite ID {invite.id} to {invite.email} for organization '{organization_name}'.")
    except Exception as e:
        logger.error(f"Failed to send invite email for invite ID {invite.id} to {invite.email}: {e}", exc_info=True)
        # Decide if you want to raise an error back to the user or just log it.
        # For now, we just log it, the invite is still created. 