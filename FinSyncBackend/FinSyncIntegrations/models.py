# FinSyncIntegrations/models.py
import uuid
import logging
from django.db import models
from django.utils import timezone
from django.conf import settings # For AUTH_USER_MODEL

# Import Organization model using string reference
# from FinSyncOrganizations.models import Organization # Avoid direct import

logger = logging.getLogger(__name__)

# TODO: Implement actual encryption/decryption for sensitive fields

class Integration(models.Model):
    """
    Represents a connection from an Organization to an external service
    (e.g., Zoho Books, QuickBooks, CRM).
    """

    class Provider(models.TextChoices):
        ZOHOBOOKS = 'zohobooks', 'Zoho Books'
        QUICKBOOKS = 'quickbooks', 'QuickBooks Online'
        # Add other providers like STRIPE, HUBSPOT, etc.

    class Status(models.TextChoices):
        CONNECTED = 'Connected', 'Connected'
        DISCONNECTED = 'Disconnected', 'Disconnected' # User manually disconnected
        NEEDS_REAUTH = 'NeedsReauth', 'Needs Reauthorization' # Token expired/revoked
        ERROR = 'Error', 'Error' # Connection/Sync failed
        PENDING_EXTERNAL_ID = 'PendingExternalID', 'Pending External ID Selection'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'FinSyncOrganizations.Organization', # String reference
        on_delete=models.CASCADE, # If Organization deleted, remove its integrations
        related_name='integrations',
        null=False # An integration must belong to an organization
    )
    provider = models.CharField(
        max_length=50,
        choices=Provider.choices,
        db_index=True
    )
    # Identifier from the external service (Zoho Org ID, QB Realm ID)
    external_id = models.CharField(
        max_length=255, blank=True, null=True, db_index=True,
        help_text="Identifier from the external provider (e.g., RealmID, OrgID). Required for most integrations."
    )
    # User-friendly name for this specific connection instance
    name = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="User-defined name for this connection (e.g., 'Main Zoho Account', 'US QB Company')."
    )
    connection_status = models.CharField(
        max_length=30, # Increased max_length
        choices=Status.choices,
        default=Status.DISCONNECTED
    )

    # --- Store Credentials Securely ---
    # ** REPLACE WITH ACTUAL ENCRYPTION IMPLEMENTATION **
    access_token_encrypted = models.TextField(blank=True, null=True, help_text="Encrypted access token")
    refresh_token_encrypted = models.TextField(blank=True, null=True, help_text="Encrypted refresh token")
    token_expiry = models.DateTimeField(null=True, blank=True, help_text="Approximate expiry time of the access token")

    # --- Audit & Status ---
    added_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # Keep integration record if user deleted
        null=True,
        blank=True,
        related_name='added_integrations',
        help_text="The user who originally established this connection."
    )
    last_successful_sync = models.DateTimeField(null=True, blank=True)
    last_sync_error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Ensure an Organization doesn't connect the *same* external account instance
        # via the *same* provider twice. External ID might be null for some simple integrations.
        unique_together = [['organization', 'provider', 'external_id']]
        ordering = ['organization__name', 'provider', 'created_at']
        verbose_name = "Integration"
        verbose_name_plural = "Integrations"

    def __str__(self):
        org_name = getattr(self.organization, 'name', 'Detached Org')
        ext_id_part = f" ({self.external_id})" if self.external_id else ""
        return f"{self.get_provider_display()}{ext_id_part} for {org_name} [{self.connection_status}]"

    # --- Placeholder Encryption Methods ---
    # Replace these with your actual encryption implementation
    def set_tokens(self, access_token, refresh_token, expires_in_seconds=None):
        # self.access_token_encrypted = encrypt(access_token)
        # self.refresh_token_encrypted = encrypt(refresh_token)
        self.access_token_encrypted = access_token # REMOVE THIS LINE AFTER IMPLEMENTING ENCRYPTION
        self.refresh_token_encrypted = refresh_token # REMOVE THIS LINE AFTER IMPLEMENTING ENCRYPTION
        logger.warning(f"Storing unencrypted tokens for Integration {self.id}. IMPLEMENT ENCRYPTION!") # Add logging warning

        if expires_in_seconds:
             # Store with a buffer (e.g., 95% of duration)
            buffer_factor = 0.95
            expiry_delta = timezone.timedelta(seconds=int(expires_in_seconds * buffer_factor))
            self.token_expiry = timezone.now() + expiry_delta
        else:
            self.token_expiry = None
        # Note: Saving should happen after calling this in the view/task

    def get_access_token(self):
        if not self.access_token_encrypted: return None
        # return decrypt(self.access_token_encrypted)
        return self.access_token_encrypted # REMOVE THIS LINE

    def get_refresh_token(self):
        if not self.refresh_token_encrypted: return None
        # return decrypt(self.refresh_token_encrypted)
        return self.refresh_token_encrypted # REMOVE THIS LINE
    # --- End Placeholder Methods ---

    @property
    def is_connected(self):
        return self.connection_status == self.Status.CONNECTED

    @property
    def needs_refresh(self):
        """Check if the access token is likely expired or close to expiring."""
        if not self.is_connected or not self.token_expiry:
            return False # Cannot refresh if not connected or no expiry info
        # Refresh slightly before expiry (e.g., 5-10 minutes)
        refresh_buffer = timezone.timedelta(minutes=10)
        return timezone.now() >= (self.token_expiry - refresh_buffer)


class OAuthState(models.Model):
    """
    Generic OAuth state storage for CSRF protection across all providers.
    Used during OAuth flow to validate callbacks.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = models.CharField(max_length=255, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='oauth_states'
    )
    organization = models.ForeignKey(
        'FinSyncOrganizations.Organization',
        on_delete=models.CASCADE,
        related_name='oauth_states'
    )
    provider = models.CharField(
        max_length=50,
        choices=Integration.Provider.choices,
        help_text="The integration provider this state is for"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    # Optional: Store additional provider-specific data
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional provider-specific data needed during OAuth flow"
    )
    
    class Meta:
        verbose_name = "OAuth State"
        verbose_name_plural = "OAuth States"
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['provider', 'created_at']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            # Set expiration to 10 minutes from creation
            self.expires_at = timezone.now() + timezone.timedelta(minutes=10)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @classmethod
    def create_for_provider(cls, user, organization, provider, extra_data=None):
        """Create a new OAuth state for a specific provider."""
        state_value = uuid.uuid4().hex
        return cls.objects.create(
            state=state_value,
            user=user,
            organization=organization,
            provider=provider,
            extra_data=extra_data or {}
        )
    
    @classmethod
    def validate_and_get(cls, state_value, provider):
        """
        Validate a state value and return the associated data.
        Deletes the state after retrieval (one-time use).
        """
        try:
            oauth_state = cls.objects.get(
                state=state_value,
                provider=provider,
                expires_at__gt=timezone.now()
            )
            user_id = oauth_state.user_id
            org_id = oauth_state.organization_id
            extra_data = oauth_state.extra_data
            
            # Delete after use (CSRF protection)
            oauth_state.delete()
            
            return {
                'user_id': user_id,
                'organization_id': org_id,
                'extra_data': extra_data
            }
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def cleanup_expired(cls):
        """Delete expired states."""
        deleted_count, _ = cls.objects.filter(expires_at__lt=timezone.now()).delete()
        if deleted_count:
            logger.info(f"Cleaned up {deleted_count} expired OAuth states")