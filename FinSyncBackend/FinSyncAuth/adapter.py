# FinSyncAuth/adapter.py
import logging
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.db.utils import IntegrityError

# Import Organization and SubscriptionPlan models correctly
from FinSyncOrganizations.models import Organization, SubscriptionPlan, OrganizationInvite
from FinSyncOrganizations.utils import apply_trial_plan_to_organization

logger = logging.getLogger(__name__)

# --- Optional: List of common free email domains to exclude from org creation prompts ---
# --- Store this in settings.py or a database table for easier management ---
FREE_EMAIL_DOMAINS = getattr(settings, 'FREE_EMAIL_DOMAINS', {
    'gmail.com', 'googlemail.com', 'hotmail.com', 'outlook.com', 'live.com',
    'yahoo.com', 'aol.com', 'msn.com', 'icloud.com',
})


class CustomAccountAdapter(DefaultAccountAdapter):

    @transaction.atomic
    def save_user(self, request, user, form, commit=True):
        """
        Overrides the default save_user to handle organization linking/creation:
        1. Joins via invite ID if provided.
        2. Creates a new named organization if name is provided.
        3. Creates an individual/personal organization as a fallback.
        """
        # Handle save_user for both regular allauth forms and our custom Form
        if hasattr(form, 'cleaned_data'):
            # Our custom form or any form with cleaned_data already populated
            user = super().save_user(request, user, form, commit=False)
        else:
            # For any unexpected form structure, fallback to default behavior
            user = super().save_user(request, user, form, commit=False)
            
        organization_name_from_form = form.cleaned_data.get('organization_name')
        organization_invite_id_from_form = form.cleaned_data.get('organization_invite_id')

        user_email = user.email
        user_domain = user.get_domain()

        organization_to_associate = None
        was_organization_newly_created = False # Flag to track if we create an org
        invite_object = None # Keep track of the invite to mark it used later

        # Assume organization_invite_id_from_form holds the INVITE CODE
        if organization_invite_id_from_form:
            invite_code = organization_invite_id_from_form # Rename for clarity
            try:
                # 1. Find the OrganizationInvite by code
                invite_object = OrganizationInvite.objects.select_related('organization').get(
                    code=invite_code
                )

                # 2. Validate the invite
                if not invite_object.is_active:
                    raise ValidationError(_("This invitation code is no longer active."))
                if invite_object.expires_at and invite_object.expires_at < timezone.now():
                    invite_object.is_active = False
                    invite_object.save(update_fields=['is_active']) # Mark expired
                    raise ValidationError(_("This invitation code has expired."))
                if invite_object.email and invite_object.email.lower() != user_email.lower():
                    raise ValidationError(_("This invitation is intended for a different email address."))

                # 3. Get the organization from the invite
                org_from_invite = invite_object.organization

                # 4. Check the organization status and capacity
                if not org_from_invite: # Should not happen due to FK constraints, but good practice
                     logger.error(f"Invite {invite_code} (ID: {invite_object.id}) has no associated organization.")
                     raise ValidationError(_("The invite is linked to an invalid organization."))
                if not org_from_invite.is_active:
                     raise ValidationError(_("The organization linked to this invite is currently inactive."))
                if not org_from_invite.can_add_user():
                    logger.warning(f"Org '{org_from_invite.name}' (ID: {org_from_invite.id}) is full. User '{user_email}' cannot join via invite '{invite_code}'.")
                    raise ValidationError(_("The organization you are trying to join via invite is currently full."))

                # 5. Set the organization to associate
                organization_to_associate = org_from_invite
                logger.info(f"User '{user_email}' joining Org '{org_from_invite.name}' (ID: {org_from_invite.id}) via valid invite code '{invite_code}'.")

            except OrganizationInvite.DoesNotExist:
                logger.warning(f"Invite code '{invite_code}' not found for user '{user_email}'.")
                raise ValidationError(_("The organization invite code is invalid or does not exist."))
            except ValidationError as e: # Catch specific validation errors raised above
                 raise e # Re-raise them
            except Exception as e:
                logger.error(f"Unexpected error processing invite code '{invite_code}' for user '{user_email}': {e}", exc_info=True)
                raise ValidationError(_("There was an issue processing your organization invite. Please try again or contact support."))

        if not organization_to_associate and organization_name_from_form:
            effective_domain_for_new_org = None
            if user_domain and user_domain not in FREE_EMAIL_DOMAINS:
                if not Organization.objects.filter(domain=user_domain).exists():
                    effective_domain_for_new_org = user_domain
                else:
                    logger.info(f"Domain '{user_domain}' is already associated with an existing organization. "
                                 f"New org '{organization_name_from_form}' for user '{user_email}' will not automatically claim this domain.")
            try:
                new_org_instance = Organization(
                    name=organization_name_from_form,
                    domain=effective_domain_for_new_org
                    # created_by will be set after user is saved
                )
                
                apply_trial_plan_to_organization(new_org_instance)
                
                # apply_trial_plan_to_organization is called by model's save method.
                new_org_instance.full_clean() # Validate before saving
                new_org_instance.save() # This will set owner if created_by is set and owner isn't (but created_by isn't set yet)
                organization_to_associate = new_org_instance
                was_organization_newly_created = True
                logger.info(f"Created new Organization '{new_org_instance.name}' (ID: {new_org_instance.id}) for user '{user_email}'. Domain: '{effective_domain_for_new_org}'. Will link created_by later.")
            except ValidationError as e:
                logger.error(f"Validation error creating new organization '{organization_name_from_form}' for user '{user_email}': {e.message_dict if hasattr(e, 'message_dict') else e}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"Unexpected error creating new organization '{organization_name_from_form}' for user '{user_email}': {e}", exc_info=True)
                raise ValidationError(_("Could not create the new organization. Please check the details and try again."))

        if not organization_to_associate: # Fallback: Create an individual/personal organization
            individual_org_name = f"{user_email}'s Workspace"
            try:
                individual_org_instance = Organization(
                    name=individual_org_name
                    # created_by will be set after user is saved
                )
                
                # apply_trial_plan_to_organization is called by model's save method.
                # individual_org_instance.full_clean()
                individual_org_instance.save() 
                organization_to_associate = individual_org_instance
                was_organization_newly_created = True
                logger.info(f"Created individual Organization '{individual_org_instance.name}' (ID: {individual_org_instance.id}) for user '{user_email}'. Will link created_by later.")
            except ValidationError as e:
                logger.error(f"Validation error creating individual organization for user '{user_email}': {e.message_dict if hasattr(e, 'message_dict') else e}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"Unexpected error creating individual organization for user '{user_email}': {e}", exc_info=True)
                raise ValidationError(_("We encountered an issue setting up your personal workspace. Please contact support."))

        if not organization_to_associate:
            logger.critical(f"CRITICAL: Failed to associate or create an organization for user '{user_email}'. This indicates a logic flaw in save_user.")
            raise ValidationError(_("A critical error occurred setting up your account's organization. Please contact support immediately."))

        user.organization = organization_to_associate

        if commit:
            user.save() # Save the user. Now user has an ID and organization_id.
            logger.info(f"User '{user.email}' saved successfully with Organization '{user.organization.name}' (ID: {user.organization.id}).")

            # If an invite was successfully used, mark it now that the user is saved
            if invite_object and organization_to_associate == invite_object.organization:
                try:
                    invite_object.mark_used(user) # Assumes mark_used method exists
                    logger.info(f"Marked invite code '{invite_object.code}' as used by user '{user.email}'.")
                except Exception as e:
                    # Log error but don't fail the user creation
                    logger.error(f"Failed to mark invite code '{invite_object.code}' as used for user '{user.email}' after signup: {e}", exc_info=True)

            # If the organization was newly created in this transaction,
            # update it with the 'created_by' and potentially 'owner' fields now that the user has a PK.
            if was_organization_newly_created and organization_to_associate:
                update_fields_for_org = []
                if organization_to_associate.created_by_id is None:
                    organization_to_associate.created_by = user
                    update_fields_for_org.append('created_by')
                
                # Mimic Organization.save() logic for owner assignment
                if organization_to_associate.created_by_id == user.id and not organization_to_associate.owner_id:
                    organization_to_associate.owner = user
                    update_fields_for_org.append('owner')
                
                if update_fields_for_org:
                    organization_to_associate.save(update_fields=update_fields_for_org)
                    logger.info(f"Updated Organization '{organization_to_associate.name}' (ID: {organization_to_associate.id}) with fields {update_fields_for_org} linked to user '{user.email}'.")
        return user


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):

    def save_user(self, request, sociallogin, form=None):
        """
        Overrides the default social save_user.
        - Creates a new "individual" organization for the user if not already linked.
        """
        with transaction.atomic():
            user = super().save_user(request, sociallogin, form)

            if sociallogin.is_existing or user.organization_id:
                if user.organization_id:
                    logger.info(f"Social login: User '{user.email}' already linked to Org ID '{user.organization_id}'. No adapter action needed.")
                else:
                    logger.info(f"Social login: Existing user '{user.email}' found but not linked to an organization. Will attempt to link or create one.")
                    # Pass through to org creation logic below if not linked
                # If user.organization_id is already set, we skip further org association logic.
                if user.organization_id: # Re-check after logging
                    return user


            organization_to_associate = user.organization # Should be None if we reach here and user wasn't linked

            email = getattr(user, 'email', None)
            if not email and sociallogin.account.extra_data:
                email = sociallogin.account.extra_data.get('email')

            # user_domain = None # Not needed anymore for domain joining
            # if email:
            #     try:
            #         user_domain = email.split('@')[1].lower()
            #     except IndexError:
            #         pass
            
            if not email:
                logger.warning(f"Social login: Cannot determine organization for user (social ID: {sociallogin.account.uid}, provider: {sociallogin.account.provider}) due to missing email. User will not be linked to an organization by this adapter.")
                # This is problematic if user.organization is mandatory.
                # However, CustomUser model makes it mandatory.
                # If email is missing, we cannot form a name like "email's workspace".
                # This scenario implies a user record might be created without an org if email is missing.
                # The super().save_user might have already saved the user.
                # This needs to be handled carefully. If user.email is null, creating user will fail at DB level.
                # For now, assume email is present due to model constraints on CustomUser.
                # If not, a critical error will occur later or at CustomUser.save()
                return user # Cannot proceed without email for naming the individual org

            # --- Removed "Join by Domain" Logic for Social Adapter ---
            # if not organization_to_associate and user_domain and user_domain not in FREE_EMAIL_DOMAINS:
            #     try:
            #         existing_org_by_domain = Organization.objects.get(
            #             domain=user_domain,
            #             is_active=True
            #         )
            #         if existing_org_by_domain.can_add_user():
            #             organization_to_associate = existing_org_by_domain
            #             logger.info(f"Social Login: User '{email}' joining existing Org '{existing_org_by_domain.name}' based on domain '{user_domain}'.")
            #         else:
            #             logger.warning(f"Social Login: Org '{existing_org_by_domain.name}' (domain: {user_domain}) is full. User '{email}' cannot auto-join.")
            #     except Organization.DoesNotExist:
            #         logger.info(f"Social Login: No existing org found for domain '{user_domain}' for user '{email}'.")
            #     except Exception as e:
            #         logger.error(f"Social Login: Error checking org for domain '{user_domain}' for user '{email}': {e}", exc_info=True)

            if not organization_to_associate: # This will always be true here unless user was already linked
                individual_org_name = f"{email}'s Workspace"
                try:
                    individual_org = Organization(
                        name=individual_org_name,
                        created_by=user
                    )
                    
                    # apply_trial_plan_to_organization is called by model's save method.

                    individual_org.full_clean()
                    individual_org.save() # This will set owner and plan
                    organization_to_associate = individual_org
                    logger.info(f"Social Login: Created individual Org '{individual_org.name}' for user '{email}'.")
                except ValidationError as e:
                    logger.error(f"Social Login: Validation error creating individual organization for user '{email}': {e}", exc_info=True)
                    raise
                except Exception as e:
                    logger.error(f"Social Login: Unexpected error creating individual org for user '{email}': {e}", exc_info=True)
                    raise

            if organization_to_associate and user.organization_id != organization_to_associate.id:
                user.organization = organization_to_associate
                user.save(update_fields=['organization'])
                logger.info(f"Social login: User '{user.email}' organization updated/set to '{user.organization.name}' (ID: {user.organization.id}).")
            elif not user.organization_id and not organization_to_associate:
                 logger.critical(f"Social login: User '{user.email}' ended up without an organization after processing. This is a bug.")
                 raise IntegrityError(f"User {user.email} could not be associated with an organization during social login.")

        return user

    def validate_disconnect(self, account, accounts):
        """Prevent disconnecting last social account if no password is set."""
        if len(accounts) <= 1:
            has_password = account.user.has_usable_password()
            other_social = account.user.socialaccount_set.exclude(id=account.id).exists()
            if not has_password and not other_social:
                logger.warning(f"User {account.user.email} attempted to disconnect last auth method (Social: {account.provider}) without a password set.")
                raise ValidationError(
                    _("You cannot disconnect your only login method. Please set a password first.")
                )
        return super().validate_disconnect(account, accounts)