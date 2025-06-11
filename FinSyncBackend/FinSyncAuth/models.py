# FinSyncAuth/models.py
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings
import logging

# Import Organization model using string reference to avoid circular imports
# if models are in different apps
# from FinSyncOrganizations.models import Organization # Avoid this direct import
from FinSyncOrganizations.models import Organization # Added for direct use in manager

logger = logging.getLogger(__name__)

class CustomUserManager(BaseUserManager):
    """Manager for CustomUser model with email as the identifier."""

    def create_user(self, email, password=None, organization=None, **extra_fields):
        """Creates and saves a User with the given email, password, and organization."""
        if not email:
            raise ValueError(_('The Email must be set'))
        if not organization:
            # This check assumes the adapter/view logic handles Org creation first
            # Or that create_superuser doesn't need one initially.
            # If called directly, Org MUST be provided unless it's a superuser setup edge case.
            pass # Allow superuser creation without org initially? Risky. Best to ensure org exists.
            # raise ValueError(_('An Organization must be provided when creating a user.'))


        email = self.normalize_email(email)
        # Ensure organization is passed if required
        extra_fields.setdefault('organization_id', getattr(organization, 'id', None))
        if not extra_fields.get('organization_id') and not extra_fields.get('is_superuser'):
             raise ValueError(_('An Organization ID must be provided.'))

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        """Creates and saves a SuperUser."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        # Superuser creation needs a temporary user instance to assign as created_by for the org.
        # This is a bit tricky as the user doesn't exist yet. We create org first, then user.
        # For the Admin Org, created_by might be null, or we defer setting it until user is created.
        # Simplest for now: create org, then create user, then update org.created_by and org.owner.

        admin_org_name = getattr(settings, 'ADMIN_ORG_NAME', 'SuperAdmin Organization')
        admin_organization = None
        try:
            # Step 1: Get or Create Admin Organization (without created_by/owner initially)
            admin_organization, created = Organization.objects.get_or_create(
                name=admin_org_name,
                defaults={'is_active': True}
            )

            if created:
                logger.info(f"Created default admin organization: {admin_org_name}. Assigning default plan...")
                # Plan assignment logic (already present and seems okay, it calls admin_organization.save())
                try:
                    from FinSyncOrganizations.models import SubscriptionPlan
                    trial_plan = SubscriptionPlan.objects.get(is_trial=True)
                except SubscriptionPlan.DoesNotExist:
                    logger.info("Default trial plan not found for admin org. Creating one.")
                    trial_plan = SubscriptionPlan.objects.create(
                        name=SubscriptionPlan.PlanName.TRIAL,
                        display_name="Trial Plan (Admin Default)", max_users=1, max_integrations=1,
                        is_trial=True, trial_duration_days=getattr(settings, 'DEFAULT_TRIAL_DURATION_DAYS', 14),
                        is_available=False
                    )
                except SubscriptionPlan.MultipleObjectsReturned:
                    logger.error("Multiple trial plans found. Cannot assign to admin org.")
                    raise ValueError("Multiple default trial plans found. Configuration error.")
                
                admin_organization.subscription_plan = trial_plan
                # created_by and owner will be set after the superuser is created.
                admin_organization.save() # Save plan and other defaults

            extra_fields['organization_id'] = admin_organization.id

        except Exception as e:
            logger.error(f"Could not get or create admin organization '{admin_org_name}': {e}", exc_info=True)
            raise ValueError(
                f"Failed to get or create the admin organization '{admin_org_name}'. "
                f"Superuser creation cannot proceed. Error: {e}"
            )
        
        # Step 2: Create the superuser (this part was mostly fine)
        # The create_user method itself doesn't set created_by on the org
        user = self.create_user(email=email, password=password, organization=admin_organization, **extra_fields)

        # Step 3: Now that superuser exists, update the Admin Organization's created_by and owner
        if admin_organization:
            if not admin_organization.created_by_id:
                admin_organization.created_by = user
            if not admin_organization.owner_id:
                 admin_organization.owner = user # The superuser owns the admin org by default
            admin_organization.save(update_fields=['created_by', 'owner'])
            logger.info(f"Set user {user.email} as created_by and owner for admin organization '{admin_org_name}'.")

        return user


class CustomUser(AbstractUser):
    """
    Custom user model using email. Every user MUST belong to an Organization.
    """
    username = None # Remove username field
    email = models.EmailField(_('email address'), unique=True, db_index=True)

    # Link to an Organization - Now MANDATORY
    organization = models.ForeignKey(
        'FinSyncOrganizations.Organization', # String reference
        on_delete=models.CASCADE, # If Organization is deleted, delete associated users.
        null=False, # Cannot be null in the database
        blank=False, # Cannot be blank in forms/admin
        related_name='members',
        help_text="The organization this user belongs to."
    )

    # Optional: User-specific fields
    # job_title = models.CharField(max_length=100, blank=True)
    # phone_number = models.CharField(max_length=20, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [] # Email and password handled by manager

    objects = CustomUserManager() # Use the custom manager

    def __str__(self):
        # Accessing organization might fail if called before org is set during creation
        org_name = getattr(getattr(self, 'organization', None), 'name', 'No Org Set')
        return f"{self.email} ({org_name})"

    def get_domain(self):
        """Extracts the domain part from the user's email, lowercase."""
        if not self.email:
            return None
        try:
            return self.email.split('@')[1].lower()
        except IndexError:
            return None

    @property
    def is_organization_member(self):
        # This will always be true now if the user record is valid
        return self.organization_id is not None

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"