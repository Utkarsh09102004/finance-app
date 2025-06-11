# FinSyncOrganizations/models.py
import logging
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from decimal import Decimal
from FinSyncOrganizations.utils import apply_trial_plan_to_organization
import uuid # For generating unique invite codes


logger = logging.getLogger(__name__)


import logging
from django.db import models
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

class SubscriptionPlan(models.Model):
    """
    Defines the available subscription plans and their limits,
    which are applied to the Organization.
    """
    class PlanName(models.TextChoices):
        TRIAL = 'trial', 'Trial'
        INDIVIDUAL = 'individual', 'Individual'
        TEAM = 'team', 'Team'
        # Add more plans like ENTERPRISE if needed

    name = models.CharField(
        max_length=50,
        choices=PlanName.choices,
        unique=True,
        primary_key=True,
        help_text="Internal identifier for the plan (trial, individual, team)."
    )
    display_name = models.CharField(
        max_length=100,
        help_text="User-facing name for the plan (e.g., 'Individual Plan', 'Team Plan (5 Users)')."
    )

    # --- Core Limits Applied to the Organization ---
    max_users = models.PositiveIntegerField(
        default=1, # Default to 1, enforce specific values in clean()
        help_text="Maximum number of active users allowed within an Organization on this plan."
    )
    max_integrations = models.PositiveIntegerField(
        default=1,
        help_text="Maximum number of active integrations (of any type) allowed for an Organization on this plan."
    )

    # --- Trial Specifics ---
    is_trial = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Designates this as the default trial plan assigned on initial organization creation."
    )
    trial_duration_days = models.PositiveIntegerField(
        default=14, null=True, blank=True,
        help_text="Duration of the trial in days (only relevant if is_trial=True)."
    )

    # --- Commercials & Availability ---
    price_monthly = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    price_annually = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    features = models.JSONField(default=dict, blank=True, help_text="List or dict of features included.")
    is_available = models.BooleanField(
        default=True,
        help_text="Can users/organizations select this plan directly (e.g., during upgrade)? Trial plan should be False."
    )

    def __str__(self):
        return self.display_name or self.get_name_display()

    def clean(self):
        """ Enforce plan-specific rules during validation. """
        if self.is_trial and not self.trial_duration_days:
            raise ValidationError("Trial plans must have a trial_duration_days.")

        if self.name == self.PlanName.INDIVIDUAL:
            if self.max_users != 1:
                logger.warning(f"Correcting max_users for Individual plan '{self.pk}' to 1.")
                self.max_users = 1
            # Optionally enforce other limits for Individual plans
            # if self.max_integrations > 1: self.max_integrations = 1

        elif self.name == self.PlanName.TEAM:
            if self.max_users is None or self.max_users <= 1:
                 raise ValidationError("Team plan must specify max_users greater than 1.")
            if self.max_integrations is None or self.max_integrations < 1:
                 raise ValidationError("Team plan must specify max_integrations of at least 1.")

        else: # Handles TRIAL or any future plans
            if self.max_users is None or self.max_users < 1:
                raise ValidationError(f"Plan '{self.name}' must have max_users >= 1.")
            if self.max_integrations is None or self.max_integrations < 1:
                raise ValidationError(f"Plan '{self.name}' must specify max_integrations >= 1.")

    class Meta:
        verbose_name = "Subscription Plan"
        verbose_name_plural = "Subscription Plans"
        ordering = ['price_monthly'] 


class Organization(models.Model):
    """
    Represents the customer entity (an individual's workspace or a team).
    Holds the subscription details and owns users and integrations.
    Every CustomUser belongs to exactly one Organization.
    """
    class SubscriptionStatus(models.TextChoices):
        TRIALING = 'trialing', 'Trialing'
        ACTIVE = 'active', 'Active'
        PAST_DUE = 'past_due', 'Past Due'
        CANCELED = 'canceled', 'Canceled'
        INACTIVE = 'inactive', 'Inactive' # e.g., Trial ended, didn't convert

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(
        max_length=255,
        help_text="Name of the organization or workspace."
    )
    # Domain is optional, useful for potential team features later
    domain = models.CharField(
        max_length=255, unique=True, db_index=True,
        null=True, blank=True, # Allow null for individual users without custom domain
        help_text="Primary email domain associated with this organization, if applicable."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="General status flag for the organization account itself."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, # Allow null for system-created orgs or if creator is deleted
        blank=True,
        related_name='created_organizations',
        help_text="User who originally created this organization.",
        editable=False # Should be set programmatically on creation
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, # Organization can be ownerless if owner account is deleted/not set
        blank=True,
        related_name='owned_organizations',
        help_text="Current administrative owner of this organization."
    )

    # --- Subscription Details (Embedded) ---
    subscription_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT, # Prevent deleting a Plan if Orgs are using it
        null=False, # Must always have a plan after creation
        blank=False,
        related_name='organizations'
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.TRIALING # Default set here, confirmed in save()
    )
    trial_ends_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Timestamp when the current trial period expires."
    )
    subscription_start_date = models.DateField(
        null=True, blank=True,
        help_text="Date the current paid subscription period started."
    )
    subscription_end_date = models.DateField(
        null=True, blank=True,
        help_text="Date the current subscription period ends (due to cancellation)."
    )

    # Optional: Payment provider details
    # stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    # stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)

    def __str__(self):
        plan_name = self.subscription_plan.get_name_display() if self.subscription_plan else "No Plan"
        return f"{self.name} ({plan_name} - {self.get_subscription_status_display()})"

    def save(self, *args, **kwargs):
        # Ensure domain is lowercase if provided
        if self.domain:
            self.domain = self.domain.lower()
        
        is_new = self._state.adding
       

        # Assign default trial plan ONLY on initial creation if no plan is set
        if is_new and self.subscription_plan_id is None:
            try:
                apply_trial_plan_to_organization(self)
            except ValidationError as e:
                raise e
            except Exception as e:
                logger.error(f"Unexpected error applying trial plan to organization: {e}", exc_info=True)
                raise ValidationError(f"Failed to set up the organization with a trial plan. Error: {e}")
        
        # Set owner to created_by if it's a new organization and owner isn't already set
        if is_new and self.created_by and not self.owner_id:
            self.owner = self.created_by

        super().save(*args, **kwargs)

    # --- Helper Methods ---

    def get_active_user_count(self):
        """Counts active users associated with this organization."""
        # Assumes related_name='members' on CustomUser.organization FK
        # Assumes CustomUser has 'is_active' field from AbstractUser
        return self.members.filter(is_active=True).count()

    def get_active_integration_count(self):
        """Counts active integrations associated with this organization."""
        # Assumes related_name='integrations' on Integration.organization FK
        # Assumes Integration has 'connection_status' field
        # You might refine what 'active' means (e.g., needs reauth still counts vs quota?)
        return self.integrations.filter(connection_status='Connected').count()

    @property
    def has_active_subscription(self):
        """Checks if the organization subscription allows core functionality."""
        active_stati = [self.SubscriptionStatus.ACTIVE, self.SubscriptionStatus.TRIALING]
        if self.subscription_status in active_stati:
            # If trialing, check expiry
            if self.subscription_status == self.SubscriptionStatus.TRIALING:
                if self.trial_ends_at and self.trial_ends_at < timezone.now():
                    # Simple check, background task should update status properly
                    return False
            return True
        return False

    def can_add_user(self):
        """Checks if another user can be added based on the current plan limits."""
        if not self.has_active_subscription:
            return False
        if not self.subscription_plan:
            logger.error(f"Org '{self.name}' (ID:{self.id}) cannot check user limit: subscription_plan is null.")
            return False # Should not happen if validation/save logic is correct

        # Compare current active user count to plan limit
        return self.get_active_user_count() < self.subscription_plan.max_users

    def can_add_integration(self):
        """Checks if another integration can be added based on the current plan limits."""
        if not self.has_active_subscription:
            return False
        if not self.subscription_plan:
            logger.error(f"Org '{self.name}' (ID:{self.id}) cannot check integration limit: subscription_plan is null.")
            return False

    

        return self.get_active_integration_count() < self.subscription_plan.max_integrations

    class Meta:
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"
        ordering = ['name']


def default_invite_code():
    """Generates a unique, somewhat human-readable invite code."""
    # Example: ORG-A2B4C6E8 (prefix + short UUID)
    return f"ORG-{uuid.uuid4().hex[:8].upper()}"

def default_invite_expiry():
    """Default expiry for an invite code (e.g., 7 days from now)."""
    return timezone.now() + timedelta(days=getattr(settings, 'DEFAULT_INVITE_EXPIRY_DAYS', 7))

class OrganizationInvite(models.Model):
    """
    Represents an invitation for a user to join an organization.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='invites',
        help_text="The organization this invite belongs to."
    )
    code = models.CharField(
        max_length=50, 
        unique=True, 
        default=default_invite_code, 
        db_index=True,
        help_text="Unique invite code."
    )
    email = models.EmailField(
        null=True, 
        blank=True, 
        db_index=True,
        help_text="If set, this invite is specifically for this email address."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # Keep invite even if inviter is deleted
        null=True,
        related_name='created_invites',
        help_text="The user who created this invite."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this invite code can still be used."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        default=default_invite_expiry,
        null=True, 
        blank=True,
        help_text="When this invite code expires. Null means it never expires."
    )
    # Optional: Track who accepted and when
    # accepted_by = models.ForeignKey(
    #     settings.AUTH_USER_MODEL,
    #     on_delete=models.SET_NULL,
    #     null=True, blank=True,
    #     related_name='accepted_invites'
    # )
    # accepted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Invite code {self.code} for {self.organization.name}"

    def clean(self):
        super().clean()
        if self.expires_at and self.expires_at < timezone.now():
            # This check is more for admin/creation time. Active status is primary for usage.
            logger.warning(f"Invite {self.code} is being created/saved with an expiry date in the past.")
        # Ensure organization exists and is active if creating an invite
        if not self.organization_id:
             raise ValidationError("An invite must be associated with an organization.")

    def mark_used(self, user_accepted):
        """Marks the invite as used."""
        self.is_active = False
        # self.accepted_by = user_accepted # If tracking accepted_by
        # self.accepted_at = timezone.now()
        self.save(update_fields=['is_active']) #, 'accepted_by', 'accepted_at'])
        logger.info(f"Invite code {self.code} for {self.organization.name} marked as used by {user_accepted.email}.")

    class Meta:
        verbose_name = "Organization Invite"
        verbose_name_plural = "Organization Invites"
        ordering = ['-created_at']

class OrganizationMembershipLog(models.Model):
    """
    Logs membership changes within organizations.
    """
    class Action(models.TextChoices):
        JOINED_ORG_VIA_SIGNUP = 'joined_signup', 'Joined via Signup'
        JOINED_ORG_VIA_INVITE = 'joined_invite', 'Joined via Invite'
        LEFT_ORG = 'left_org', 'Left Organization'
        REMOVED_BY_ADMIN = 'removed_admin', 'Removed by Admin'
        # Could add other actions like ROLE_CHANGED if you implement roles

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, # Keep log even if user is deleted
        null=True, # User might be deleted
        related_name='organization_logs'
    )
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.SET_NULL, # Keep log even if org is deleted
        null=True, # Org might be deleted
        related_name='membership_logs'
    )
    action = models.CharField(
        max_length=20,
        choices=Action.choices,
        help_text="The type of membership action that occurred."
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True, # Actor is null if user left themselves or joined via signup
        related_name='performed_org_actions',
        help_text="The user who initiated the action (e.g., admin who removed member, or user who invited). Null if self-initiated or system."
    )
    # Optional: Store details like the user's role at the time of action if you have roles
    # details = models.JSONField(null=True, blank=True, help_text="Additional details about the event, e.g., role at the time.")

    def __str__(self):
        user_email = getattr(self.user, 'email', 'N/A')
        org_name = getattr(self.organization, 'name', 'N/A')
        actor_email = getattr(self.actor, 'email', 'System/Self') if self.actor else 'System/Self'
        return f"{user_email} {self.get_action_display()} for Org '{org_name}' at {self.timestamp.strftime('%Y-%m-%d %H:%M')} (Actor: {actor_email})"

    class Meta:
        verbose_name = "Organization Membership Log"
        verbose_name_plural = "Organization Membership Logs"
        ordering = ['-timestamp']