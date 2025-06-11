from django.shortcuts import render, get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError as DRFValidationError
from django.utils import timezone
from django.db import transaction
import logging
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError

from FinSyncOrganizations.models import Organization, OrganizationInvite, OrganizationMembershipLog
from FinSyncOrganizations.serializers import (
    OrganizationInviteSerializer, 
    OrganizationInviteCreateSerializer,
    OrganizationInviteAcceptSerializer,
    OrganizationChangeOwnerSerializer,
    OrganizationCreateSerializer,
    OrganizationDetailSerializer
)
from FinSyncOrganizations.utils import apply_trial_plan_to_organization, send_organization_invite_email
from FinSyncAuth.models import CustomUser

logger = logging.getLogger(__name__)

class IsOrganizationMember(permissions.BasePermission):
    """
    Custom permission to only allow members of an organization to access/edit it.
    Assumes the view has a 'organization_id' in the URL kwargs.
    """
    def has_permission(self, request, view):
        organization_id = view.kwargs.get('organization_id')
        if not organization_id:
            # This is a programming error if reached, URL conf should ensure org_id.
            logger.error("IsOrganizationMember: organization_id not found in view.kwargs")
            return False
        try:
            # Ensure the user making the request is part of the organization they are trying to affect.
            # This doesn't check if the organization_id itself is valid, get_object will do that.
            return request.user.is_authenticated and request.user.organization_id == organization_id
        except AttributeError:
            # Handles cases where user.organization_id might not exist (e.g. AnonymousUser)
            logger.warning("IsOrganizationMember: request.user has no organization_id or is not authenticated.")
            return False

    def get_object(self): # Helper for the view to get the organization, not part of permission itself
        organization_id = self.kwargs.get('organization_id')
        organization = get_object_or_404(Organization, id=organization_id)
        # Double check permission (already done by has_permission, but good for direct calls)
        if self.request.user.organization != organization:
            raise PermissionDenied("You do not have permission to access this organization.")
        return organization

class OrganizationInviteListCreateAPIView(generics.ListCreateAPIView):
    """
    API endpoint for listing and creating organization invites.
    - GET: Lists invites for a specific organization (org members only).
    - POST: Creates an invite for a specific organization (org members only).
      Returns the created invite, including the code, and sends an email if an email address is provided.
    """
    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]
    lookup_url_kwarg = 'organization_id' 
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OrganizationInviteCreateSerializer
        return OrganizationInviteSerializer # Used for GET (list) and response of POST

    def get_queryset(self):
        organization_id = self.kwargs.get(self.lookup_url_kwarg)
        # IsOrganizationMember permission already ensures user is part of this org
        return OrganizationInvite.objects.filter(organization_id=organization_id).order_by('-created_at')

    def perform_create(self, serializer):
        organization_id = self.kwargs.get(self.lookup_url_kwarg)
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.") # Should be caught by permission

        # Pass organization to serializer context for validation (e.g. unique email invite check)
        invite = serializer.save(
            organization=organization, 
            created_by=self.request.user
        )
        
        # Send email if an email address was provided in the invite
        if invite.email:
            try:
                send_organization_invite_email(invite)
            except Exception as e:
                # Log the error but don't fail the invite creation itself
                logger.error(f"Failed to send invite email for invite {invite.id} to {invite.email} during creation: {e}", exc_info=True)
        
        self.created_instance = invite # Store for create()

    def create(self, request, *args, **kwargs):
        """ Override create to ensure the detailed OrganizationInviteSerializer is used for the response. """
        serializer = self.get_serializer(data=request.data) # This will use OrganizationInviteCreateSerializer
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer) # Sets self.created_instance
        
        # Explicitly serialize the created instance with the OrganizationInviteSerializer for the response
        # This ensures the 'code' and other details are in the response.
        response_serializer = OrganizationInviteSerializer(self.created_instance, context=self.get_serializer_context())
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def get_serializer_context(self):
        """ Add view to context for serializer, e.g., for validation. """
        context = super().get_serializer_context()
        if self.kwargs.get(self.lookup_url_kwarg):
             # Provides the Organization object to the serializer context 
             # if the serializer needs to access it (e.g. for validation logic)
            try:
                context['organization'] = Organization.objects.get(id=self.kwargs[self.lookup_url_kwarg])
            except Organization.DoesNotExist:
                context['organization'] = None # Or handle error as appropriate
        context['view'] = self # Pass the view itself for more complex context needs
        return context

class OrganizationInviteAcceptAPIView(generics.GenericAPIView):
    """
    API endpoint for accepting an organization invite.
    - POST: Accepts an invite using a code. Handles moving the user to the new org.
    """
    serializer_class = OrganizationInviteAcceptSerializer
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code']
        user = request.user

        try:
            invite = OrganizationInvite.objects.select_related('organization', 'organization__subscription_plan').get(code=code)
        except OrganizationInvite.DoesNotExist:
            raise NotFound("Invite code not found or is invalid.")

        if not invite.is_active:
            raise DRFValidationError({"detail": "This invite code is no longer active."}) 

        if invite.expires_at and invite.expires_at < timezone.now():
            invite.is_active = False # Mark as inactive if expired
            invite.save(update_fields=['is_active'])
            raise DRFValidationError({"detail": "This invite code has expired."}) 

        if invite.email and invite.email.lower() != user.email.lower():
            raise PermissionDenied("This invite is intended for a different email address.")

        target_organization = invite.organization

        if user.organization == target_organization:
            # User is already a member of the target organization
            invite.mark_used(user) # Still mark invite as used if it was valid
            return Response({"detail": "You are already a member of this organization."}, status=status.HTTP_200_OK)

        if not target_organization.is_active:
            raise DRFValidationError({"detail": "The organization you are trying to join is currently inactive."}) 

        if not target_organization.can_add_user():
            raise DRFValidationError({"detail": f"Organization '{target_organization.name}' cannot accept new members at this time. It may be at its user limit."})

        current_organization = user.organization
        
        # Switch user to the new organization
        user.organization = target_organization
        user.save(update_fields=['organization'])
        
        logger.info(f"User '{user.email}' (ID: {user.id}) switched from Org '{current_organization.name if current_organization else 'None'}' (ID: {current_organization.id if current_organization else 'None'}) to Org '{target_organization.name}' (ID: {target_organization.id}) via invite '{invite.code}'.")

        invite.mark_used(user)
        
        # TODO: Consider what happens to the user's previous organization if they were the last member.
        #       If the previous org was an "individual workspace" created for them, should it be deactivated or deleted?
        #       This depends on your product logic for personal vs. team organizations.
        #       For now, we are just moving the user.

        return Response({"detail": f"Successfully joined organization: {target_organization.name}"}, status=status.HTTP_200_OK)

class LeaveOrganizationAPIView(generics.GenericAPIView):
    """
    API endpoint for a user to leave their current organization.
    When a user leaves, a new personal organization is created for them.
    """
    permission_classes = [permissions.IsAuthenticated]
    # No serializer needed as it's a simple POST action by the authenticated user.

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        user = request.user
        current_organization = user.organization

        if not current_organization:
            # Should not happen given user.organization is mandatory
            return Response({"detail": "You are not currently part of any organization."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Prevent leaving if it's the special SuperAdmin Organization (if it exists and has a specific name)
        # This is an example; adjust the name or logic as needed.
        admin_org_name = getattr(settings, 'ADMIN_ORG_NAME', 'SuperAdmin Organization')
        if current_organization.name == admin_org_name and user.is_superuser:
             # Or perhaps check if there are other superusers in this org before allowing leave.
             # For simplicity now, superusers can't make the superadmin org empty by leaving.
             # This check might be better placed if there was a concept of "primary" or "unleaveable" orgs.
            return Response({"detail": f"Cannot leave the default admin organization '{admin_org_name}' as a superuser."}, status=status.HTTP_403_FORBIDDEN)

        # Create a new personal organization for the user
        personal_org_name = f"{user.email}'s Workspace"
        try:
            # Check if a personal org with this exact name already exists for some other reason (unlikely but possible)
            # If so, maybe append a UUID or a counter. For now, assume names are unique enough or will be handled.
            personal_org = Organization(
                name=personal_org_name,
                created_by=user # Set created_by
            )
            # apply_trial_plan_to_organization(personal_org) # Utility is called by model save if plan not set
            personal_org.save() # This will also trigger plan assignment and set owner
            logger.info(f"Created new personal organization '{personal_org.name}' (ID: {personal_org.id}) for user '{user.email}'.")
        except Exception as e:
            logger.error(f"Failed to create personal organization for user '{user.email}' upon leaving: {e}", exc_info=True)
            return Response({"detail": "Could not create a personal workspace for you. Please try again or contact support."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Log leaving the current organization
        OrganizationMembershipLog.objects.create(
            user=user,
            organization=current_organization,
            action=OrganizationMembershipLog.Action.LEFT_ORG,
            actor=user # User is the actor for leaving
        )
        logger.info(f"User '{user.email}' left organization '{current_organization.name}'.")

        # Log joining the new personal organization
        OrganizationMembershipLog.objects.create(
            user=user,
            organization=personal_org,
            action=OrganizationMembershipLog.Action.JOINED_ORG_VIA_SIGNUP, # Or a new category like JOINED_PERSONAL_ORG
            actor=user
        )

        # Atomically update user's organization
        user.organization = personal_org
        user.save(update_fields=['organization'])

        # Note: The old organization `current_organization` is now orphaned if `user` was the last member.
        # No further action is taken on `current_organization` as per requirements.

        return Response({"detail": f"You have left '{current_organization.name}' and are now in your new personal workspace: '{personal_org.name}'."}, status=status.HTTP_200_OK)

class IsOrganizationOwner(permissions.BasePermission):
    """
    Custom permission to only allow the owner of an organization to perform certain actions.
    Assumes view has 'organization_id' in URL kwargs.
    """
    def has_permission(self, request, view):
        organization_id = view.kwargs.get('organization_id')
        if not organization_id:
            return False
        try:
            organization = Organization.objects.get(id=organization_id)
            # Check if the request.user is the owner of the organization
            return request.user.is_authenticated and organization.owner == request.user
        except Organization.DoesNotExist:
            return False

class OrganizationChangeOwnerAPIView(generics.GenericAPIView):
    """
    API endpoint for the current owner of an organization to change its owner.
    """
    serializer_class = OrganizationChangeOwnerSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationOwner]

    @transaction.atomic
    def post(self, request, organization_id, *args, **kwargs):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.")

        # Permission class IsOrganizationOwner already checks if request.user is the current owner.

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_owner_email = serializer.validated_data['new_owner_email']

        try:
            new_owner = CustomUser.objects.get(email__iexact=new_owner_email)
        except CustomUser.DoesNotExist: 
            # This should be caught by serializer validation, but as a safeguard:
            raise DRFValidationError({"new_owner_email": "User with this email does not exist."}) 

        # Check if the new owner is part of the organization
        if new_owner.organization != organization:
            raise DRFValidationError({"new_owner_email": f"User {new_owner_email} is not a member of this organization. They must join first."}) 

        if organization.owner == new_owner:
            return Response({"detail": f"{new_owner_email} is already the owner of this organization."}, status=status.HTTP_400_BAD_REQUEST)

        old_owner_email = organization.owner.email if organization.owner else "None"
        organization.owner = new_owner
        organization.save(update_fields=['owner'])

        # Log this action (optional, but good practice)
        # Consider adding a new action type to OrganizationMembershipLog or a separate audit log
        logger.info(f"Organization '{organization.name}' (ID: {organization.id}) owner changed by '{request.user.email}' from '{old_owner_email}' to '{new_owner.email}'.")

        return Response({"detail": f"Ownership of '{organization.name}' transferred to {new_owner.email}."}, status=status.HTTP_200_OK)

class OrganizationRemoveMemberAPIView(generics.GenericAPIView):
    """
    API endpoint for an organization owner to remove a member from their organization.
    The removed member is moved to a new personal organization.
    """
    permission_classes = [permissions.IsAuthenticated, IsOrganizationOwner]
    # No serializer needed as the user_id_to_remove is in the URL.

    @transaction.atomic
    def post(self, request, organization_id, user_id_to_remove, *args, **kwargs):
        admin_user = request.user
        
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.")

        # IsOrganizationOwner permission already verifies admin_user owns this organization.

        try:
            user_to_remove = CustomUser.objects.get(id=user_id_to_remove)
        except CustomUser.DoesNotExist:
            raise NotFound("User to remove not found.")

        if admin_user == user_to_remove:
            raise DRFValidationError({"detail": "Owners cannot remove themselves. Use the 'Leave Organization' endpoint instead."}) 

        if user_to_remove.organization != organization:
            raise DRFValidationError({"detail": f"User '{user_to_remove.email}' is not a member of organization '{organization.name}'."}) 

        # Create a new personal organization for the removed user
        personal_org_name = f"{user_to_remove.email}'s Workspace"
        try:
            personal_org = Organization(
                name=personal_org_name,
                created_by=user_to_remove # The user effectively 'creates' their new personal org
            )
            # The Organization.save() method will handle applying a trial plan if not set
            personal_org.save()
            logger.info(f"Created new personal organization '{personal_org.name}' for removed user '{user_to_remove.email}'.")
        except Exception as e:
            logger.error(f"Failed to create personal organization for removed user '{user_to_remove.email}': {e}", exc_info=True)
            return Response({"detail": "Could not create a personal workspace for the removed user."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Log removal from the current organization
        OrganizationMembershipLog.objects.create(
            user=user_to_remove,
            organization=organization,
            action=OrganizationMembershipLog.Action.REMOVED_BY_ADMIN,
            actor=admin_user
        )
        logger.info(f"User '{user_to_remove.email}' removed from organization '{organization.name}' by admin '{admin_user.email}'.")

        # Log joining the new personal organization
        OrganizationMembershipLog.objects.create(
            user=user_to_remove,
            organization=personal_org,
            # Consider a more specific action like JOINED_VIA_REMOVAL or JOINED_DEFAULT_WORKSPACE
            action=OrganizationMembershipLog.Action.JOINED_ORG_VIA_SIGNUP, 
            actor=admin_user # Or system/self if preferred for this auto-creation context
        )

        # Atomically update user's organization
        user_to_remove.organization = personal_org
        user_to_remove.save(update_fields=['organization'])

        return Response({"detail": f"User '{user_to_remove.email}' has been removed from '{organization.name}' and moved to a new personal workspace."}, status=status.HTTP_200_OK)

class CreateOrganizationAPIView(generics.ListCreateAPIView):
    """
    Allows authenticated users to create a new organization.
    Returns detailed information about the newly created organization.
    Note: This endpoint might be less used if org creation primarily happens during signup via the adapter.
    If used, it assumes the user is *not* already part of an organization or can create multiple.
    Consider permission logic carefully based on your product rules.
    """
    # queryset = Organization.objects.all() # Or filter based on permissions
    permission_classes = [permissions.IsAuthenticated] # Basic permission
    serializer_class = OrganizationCreateSerializer # Use simple serializer for request payload

    def get_serializer_class(self):
        """ Use create serializer for request, detail serializer for response """
        if self.request.method == 'POST':
            return OrganizationCreateSerializer
        # If you add GET support (ListAPIView), you might want DetailSerializer here too
        # return OrganizationDetailSerializer 
        return super().get_serializer_class()

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        
        # --- Check Permissions/Business Logic --- 
        # Example: Prevent user from creating if already in an org
        # if hasattr(user, 'organization') and user.organization is not None:
        #     raise PermissionDenied("You already belong to an organization.")

        org_name = serializer.validated_data.get('name')
        logger.info(f"User '{user.email}' attempting to create organization '{org_name}'.")

        try:
            organization = Organization(name=org_name)
            # apply_trial_plan will be called by Organization.save()
            organization.save() # Save the org first. This will call apply_trial_plan if needed.


            organization.created_by = user
            organization.owner = user
            organization.save(update_fields=['created_by', 'owner'])
            
            # IMPORTANT: Associate the user with this new organization
            # This might depend on your user model structure and business rules
            if hasattr(user, 'organization') and user.organization is None:
                 user.organization = organization
                 user.save(update_fields=['organization'])
                 logger.info(f"Associated user '{user.email}' with newly created organization '{organization.name}'.")
            else:
                # Handle cases where user might already have an org or model doesn't auto-link
                logger.warning(f"User '{user.email}' created organization '{organization.name}' but was not automatically associated. User's current org: {getattr(user, 'organization', 'N/A')}")

            logger.info(f"Organization '{organization.name}' (ID: {organization.id}) created successfully by user '{user.email}'.")
            
            # Return the newly created object for response serialization
            # DRF handles using the appropriate serializer (defined by get_serializer_class for GET/response)
            # However, ListCreateAPIView uses the main serializer_class for the response by default.
            # We need to explicitly serialize with the Detail serializer for the response here.
            
            # Instance to be returned for the response
            self.created_instance = organization

        except DjangoValidationError as e: # Catch Django's ValidationError
            logger.error(f"Django validation error creating organization '{org_name}' for user '{user.email}': {e}", exc_info=True)
            # Raise as DRFValidationError for proper API response
            raise DRFValidationError({"detail": f"Failed to create organization: {e}"}) 
        except Exception as e:
            logger.error(f"Unexpected error creating organization '{org_name}' for user '{user.email}': {e}", exc_info=True)
            raise DRFValidationError({"detail": "An unexpected error occurred while creating the organization."})

    def create(self, request, *args, **kwargs):
        """ Override create to use the Detail Serializer for the response """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer) # perform_create now sets self.created_instance
        
        # Explicitly serialize the created instance with the Detail Serializer
        response_serializer = OrganizationDetailSerializer(self.created_instance, context=self.get_serializer_context())
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class MyOrganizationDetailView(generics.RetrieveAPIView):
    """
    Returns details of the organization the currently authenticated user belongs to.
    Includes subscription details.
    """
    serializer_class = OrganizationDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        user = self.request.user
        organization = getattr(user, 'organization', None)
        if organization is None:
            logger.warning(f"User '{user.email}' attempted to access organization details but is not associated with any.")
            raise NotFound("You are not associated with an organization.")
        
        # Optionally, check if the organization is active, etc.
        # if not organization.is_active:
        #     raise PermissionDenied("Your organization is currently inactive.")
            
        logger.debug(f"User '{user.email}' fetching details for organization '{organization.name}' (ID: {organization.id}).")
        return organization


