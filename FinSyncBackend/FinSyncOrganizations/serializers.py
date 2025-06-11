from rest_framework import serializers
from django.utils import timezone
from FinSyncOrganizations.models import Organization, OrganizationInvite, OrganizationMembershipLog, SubscriptionPlan
from FinSyncAuth.models import CustomUser # For created_by context if needed, though typically set in view
from django.contrib.auth import get_user_model

User = get_user_model()

class OrganizationInviteSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying OrganizationInvite details.
    """
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model = OrganizationInvite
        fields = [
            'id', 'organization', 'organization_name', 'code', 'email', 
            'created_by', 'created_by_email', 'is_active', 
            'created_at', 'expires_at'
        ]
        read_only_fields = ['id', 'organization', 'code', 'created_by', 'created_at', 'organization_name', 'created_by_email']

class OrganizationInviteCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating an OrganizationInvite.
    Organization and created_by will be set in the view.
    """
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    # expires_at can be optionally provided, otherwise model default is used.
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = OrganizationInvite
        fields = ['email', 'expires_at'] # Fields user can provide when creating

    def validate_email(self, value):
        if value: # If email is provided, normalize it or check its validity further if needed
            return value.lower()
        return value

    def validate_expires_at(self, value):
        if value and value < timezone.now():
            raise serializers.ValidationError("Expiration date cannot be in the past.")
        return value

    def validate_email(self, value):
        # Optional: Check if an active invite already exists for this email in this org
        if value:
            # Get organization directly from context provided by the view
            organization = self.context.get('organization') 
            
            if not organization:
                # This should ideally not be reached if URL/Permissions are correct,
                # but provides a safeguard and clearer error.
                raise serializers.ValidationError("Cannot validate email: Organization context not found or invalid.")

            if OrganizationInvite.objects.filter(
                organization=organization, # Use the organization from context
                email__iexact=value,
                is_active=True,
                expires_at__gt=timezone.now()
            ).exists():
                raise serializers.ValidationError("An active invite already exists for this email address in this organization.")
        return value

class OrganizationInviteAcceptSerializer(serializers.Serializer):
    """
    Serializer for accepting an invite.
    """
    code = serializers.CharField(max_length=50, required=True)

    def validate_code(self, value):
        # Basic validation, more detailed checks will be in the view
        if not value:
            raise serializers.ValidationError("Invite code is required.")
        return value.strip()

class OrganizationChangeOwnerSerializer(serializers.Serializer):
    """
    Serializer for changing the owner of an organization.
    """
    new_owner_email = serializers.EmailField(required=True, write_only=True)

    def validate_new_owner_email(self, value):
        try:
            # Ensure the new owner exists
            CustomUser.objects.get(email__iexact=value, is_active=True)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist or is not active.")
        return value.lower()

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            'name',
            'display_name',
            'max_users',
            'max_integrations',
            'is_trial',
            'trial_duration_days',
            'price_monthly',
            'price_annually',
            'features'
        ]

class OwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name'] # Add other relevant user fields

class OrganizationDetailSerializer(serializers.ModelSerializer):
    subscription_plan = SubscriptionPlanSerializer(read_only=True)
    owner = OwnerSerializer(read_only=True)
    created_by = OwnerSerializer(read_only=True)

    class Meta:
        model = Organization
        fields = [
            'id',
            'name',
            'domain',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'owner',
            'subscription_plan',
            'subscription_status',
            'trial_ends_at',
            'subscription_start_date',
            'subscription_end_date',
            # Add other fields you want exposed
        ]
        read_only_fields = [ # Fields not expected during creation via this serializer directly
            'id',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'owner',
            'subscription_plan',
            'subscription_status',
            'trial_ends_at',
            'subscription_start_date',
            'subscription_end_date',
        ]

class OrganizationCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new organization.
    The user making the request will be set as the owner and creator.
    """
    name = serializers.CharField(max_length=255, required=True)
    # Domain is optional, can be added later if needed by uncommenting
    # domain = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Organization
        fields = ['name'] # Add 'domain' here if uncommented above
        # Exclude fields like subscription_plan, owner, created_by as they are set programmatically

    def validate_name(self, value):
        # Basic validation, can be expanded (e.g., check for profanity, reserved names)
        if not value.strip():
            raise serializers.ValidationError("Organization name cannot be empty.")
        # Optional: Check for uniqueness if desired, though multiple orgs can have the same name by default
        # if Organization.objects.filter(name=value).exists():
        #     raise serializers.ValidationError("An organization with this name already exists.")
        return value 