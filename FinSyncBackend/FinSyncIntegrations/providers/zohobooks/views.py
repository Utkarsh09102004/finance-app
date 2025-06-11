import uuid
import requests
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from FinSyncIntegrations.models import Integration, OAuthState
from .utils import get_valid_access_token
from rest_framework.authentication import SessionAuthentication, TokenAuthentication

logger = logging.getLogger(__name__)

class ZohoBooksInitiateView(APIView):
    permission_classes = [IsAuthenticated]


    def get(self, request, *args, **kwargs):
        organization = request.user.organization
        if not organization:
            return Response(
                {"error": "User does not belong to an organization."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not organization.can_add_integration():

            return Response(
                {"error": "Integration limit reached for your current plan."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Create OAuth state record for CSRF protection
        oauth_state = OAuthState.create_for_provider(
            user=request.user,
            organization=organization,
            provider=Integration.Provider.ZOHOBOOKS
        )
        state = oauth_state.state
        
        logger.info(f"[INITIATE] User: {request.user.email}, Org: {organization.name}")
        logger.info(f"[INITIATE] Created OAuth state: {state}")

        params = {
            'scope': settings.ZOHO_SCOPES,
            'client_id': settings.ZOHO_CLIENT_ID,
            'state': state,
            'response_type': 'code',
            'redirect_uri': settings.ZOHO_REDIRECT_URI,
            'access_type': 'offline',  # To get a refresh token
            'prompt': 'consent'
        }
        auth_url = f"{settings.ZOHO_AUTHORIZATION_URL}?{urlencode(params)}"
        logger.info(f"[INITIATE] auth_url: {auth_url}")
        logger.info(f"[INITIATE] Redirecting user to Zoho auth_url containing state: {state}")
        
        # Include state in response so frontend can store it as well
        return Response({
            'authorization_url': auth_url,
            'state': state,
            'user_id': request.user.id,
            'org_id': organization.id
        })


class ZohoBooksCallbackView(APIView):
    # No IsAuthenticated here initially as Zoho redirects without auth headers.
    # We verify user indirectly via the 'state' and then can link to org.


    def get(self, request, *args, **kwargs):
        logger.info(f"[CALLBACK] Callback received. Full GET params: {request.GET.urlencode()}")
        
        received_state = request.GET.get('state')
        
        logger.info(f"[CALLBACK] Received state from Zoho: {received_state}")

        if not received_state:
            logger.warning("[CALLBACK] OAuth state missing from callback. Unable to validate")
            return redirect(f"{settings.FRONTEND_INTEGRATION_FAILURE_URL}?error=state_missing")

        # Validate state and get user/org info
        state_data = OAuthState.validate_and_get(
            state_value=received_state,
            provider=Integration.Provider.ZOHOBOOKS
        )
        
        if not state_data:
            logger.error(f"[CALLBACK] Invalid or expired state: {received_state}")
            return redirect(f"{settings.FRONTEND_INTEGRATION_FAILURE_URL}?error=invalid_state")
        
        user_id = state_data['user_id']
        org_id = state_data['organization_id']
        logger.info(f"[CALLBACK] Validated state for User ID: {user_id}, Org ID: {org_id}")

        code = request.GET.get('code')
        if not code:
            logger.error("No authorization code received from Zoho.")
            return redirect(f"{settings.FRONTEND_INTEGRATION_FAILURE_URL}?error=no_code")

        # Exchange code for tokens
        token_payload = {
            'client_id': settings.ZOHO_CLIENT_ID,
            'client_secret': settings.ZOHO_CLIENT_SECRET,
            'redirect_uri': settings.ZOHO_REDIRECT_URI,
            'code': code,
            'grant_type': 'authorization_code'
        }
        response_obj = None # To store response for logging in case of error
        try:
            logger.info("Exchanging authorization code for tokens with Zoho.")
            response_obj = requests.post(settings.ZOHO_TOKEN_URL, data=token_payload, timeout=10)
            response_obj.raise_for_status()  # Raise HTTPError for bad responses (4XX, 5XX)
            token_data = response_obj.json()
            print("token_data :", token_data)
            logger.info("Successfully received tokens from Zoho.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Token exchange request failed: {e}", exc_info=True)
            error_message = "token_exchange_failed"
            if response_obj is not None and response_obj.content:
                 try:
                     error_details = response_obj.json()
                     logger.error(f"Zoho error details: {error_details}")
                 except ValueError:
                     logger.error(f"Zoho raw error response: {response_obj.text}")
            return redirect(f"{settings.FRONTEND_INTEGRATION_FAILURE_URL}?error={error_message}")

        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token') # Zoho usually provides this if access_type=offline
        expires_in = token_data.get('expires_in') # Seconds

        if not access_token:
            logger.error("Access token not found in Zoho's response.")
            return redirect(f"{settings.FRONTEND_INTEGRATION_FAILURE_URL}?error=no_access_token")

        # Get user/org from the state parameter (already extracted above)
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # user_id and org_id are already extracted from state above

        try:
            user = User.objects.get(id=user_id)
            organization = user.organization  # Or fetch by org_id if preferred
        except User.DoesNotExist:
            logger.error("User from session not found.")
            return redirect(f"{settings.FRONTEND_INTEGRATION_FAILURE_URL}?error=user_not_found")

        try:
            # Ensure an organization doesn't try to start configuring the same provider twice if one is already pending
            # This check helps prevent duplicate PENDING_EXTERNAL_ID integrations for the same provider.
            # The final unique constraint (org, provider, external_id) will apply once external_id is set.
            existing_pending_integration = Integration.objects.filter(
                organization=organization,
                provider=Integration.Provider.ZOHOBOOKS,
                connection_status=Integration.Status.PENDING_EXTERNAL_ID
            ).first()

            if existing_pending_integration:
                integration = existing_pending_integration
                created = False
                logger.info(f"Found existing PENDING_EXTERNAL_ID integration (ID: {integration.id}) for org {organization.name}. Reusing it.")
            else:
                # If no pending, check for an already fully connected one to avoid issues before external_id is set.
                # This is more of a safeguard; ideally, frontend checks prevent re-initiating if already connected.
                # However, external_id can be null before it's set, so the unique_together constraint on external_id doesn't apply yet.
                # We can create a temporary one, and then when setting external_id, we can use update_or_create with external_id.
                logger.info(f"Creating new integration record for Org ID: {organization.id}, provider: Zoho Books, status: PENDING_EXTERNAL_ID")
                integration = Integration.objects.create(
                    organization=organization,
                    provider=Integration.Provider.ZOHOBOOKS,
                    # external_id will be set later
                    name=f"Zoho Books - {organization.name} (Pending Configuration)",
                    connection_status=Integration.Status.PENDING_EXTERNAL_ID,
                    added_by_user=user
                )
                created = True

            # IMPORTANT: Implement actual encryption for set_tokens
            integration.set_tokens(access_token, refresh_token, expires_in)
            integration.save()
            
            logger.info(f"{'Created' if created else 'Updated'} Zoho Books integration (ID: {integration.id}) for org {organization.name}. Status: PENDING_EXTERNAL_ID.")

        except Exception as e:
            logger.error(f"Error saving integration for org {organization.name}: {e}", exc_info=True)
            return redirect(f"{settings.FRONTEND_INTEGRATION_FAILURE_URL}?error=integration_save_failed")

        # Redirect to frontend to handle Zoho Organization ID selection
        config_redirect_url = f"{settings.FRONTEND_INTEGRATION_PENDING_CONFIG_URL}?integration_id={integration.id}&provider=zohobooks"
        return redirect(config_redirect_url)

class ZohoBooksFetchExternalOrganizationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, integration_id, *args, **kwargs):
        try:
            integration = Integration.objects.get(
                id=integration_id,
                organization=request.user.organization,
                provider=Integration.Provider.ZOHOBOOKS
            )
        except Integration.DoesNotExist:
            return Response({"error": "Integration not found or access denied."}, status=status.HTTP_404_NOT_FOUND)

        access_token = get_valid_access_token(integration)

        if not access_token:
            # Check the status on the integration object to determine the specific error for the frontend
            if integration.connection_status == Integration.Status.NEEDS_REAUTH:
                logger.warning(f"Access token for ZB integration {integration.id} requires re-authentication.")
                return Response(
                    {"error": "reauthorization_required", 
                     "detail": "Connection to Zoho Books requires re-authorization.",
                     "provider": "zohobooks",
                     "integration_id": integration.id
                     },
                    status=status.HTTP_401_UNAUTHORIZED
                )
            logger.error(f"Failed to obtain valid access token for ZB integration {integration.id}. Current status: {integration.connection_status}")
            return Response(
                {"error": "token_unavailable", 
                 "detail": "Access token is unavailable. Please check integration status or try reconnecting."},
                status=status.HTTP_400_BAD_REQUEST # Or 401 if it implies an auth issue generically
            )

        headers = {
            'Authorization': f'Zoho-oauthtoken {access_token}',
            'Content-Type': 'application/json'
        }
        response_obj = None
        try:
            orgs_url = f"{settings.ZOHO_API_BASE_URL}/organizations"
            response_obj = requests.get(orgs_url, headers=headers, timeout=10)
            
            # If Unauthorized (e.g. token explicitly revoked from Zoho's side after our checks but before API call)
            # get_valid_access_token attempts a refresh. If it still fails and sets NEEDS_REAUTH, we catch it above.
            # This explicit 401 check after API call is a fallback for immediate revocations.
            if response_obj.status_code == 401:
                logger.warning(f"Zoho API returned 401 for integration {integration.id} despite token checks. Marking for re-auth.")
                integration.connection_status = Integration.Status.NEEDS_REAUTH
                integration.last_sync_error = "Access token rejected by Zoho (401). Re-authorization required."
                integration.save(update_fields=['connection_status', 'last_sync_error'])
                return Response(
                    {"error": "reauthorization_required", 
                     "detail": "Connection to Zoho Books was rejected. Re-authorization required.",
                     "provider": "zohobooks",
                     "integration_id": integration.id
                     },
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            response_obj.raise_for_status()
            orgs_data = response_obj.json()
            
            external_organizations = []
            if orgs_data.get('organizations'):
                for org_data in orgs_data['organizations']:
                    external_organizations.append({
                        'id': org_data.get('organization_id'),
                        'name': org_data.get('name')
                    })
            logger.info(f"Fetched {len(external_organizations)} Zoho organizations for integration {integration.id}")
            return Response(external_organizations, status=status.HTTP_200_OK)

        except requests.exceptions.HTTPError as e:
            # For other HTTP errors not caught as 401 above
            logger.error(f"HTTPError from Zoho API for integration {integration.id}: {e}. Response: {response_obj.text if response_obj else 'No response'}", exc_info=True)
            error_detail = "Failed to communicate with Zoho Books."
            if response_obj is not None: error_detail = f"Zoho API Error ({response_obj.status_code}): {response_obj.text[:100]}"
            return Response({"error": error_detail }, status=status.HTTP_502_BAD_GATEWAY) # 502 might be more apt
        except requests.exceptions.RequestException as e:
            logger.error(f"RequestException for Zoho API for integration {integration.id}: {e}", exc_info=True)
            return Response({"error": "Failed to connect to Zoho Books."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except (KeyError, IndexError, ValueError) as e: # JSON parsing or structure errors
            logger.error(f"Error parsing Zoho organizations response for integration {integration.id}: {e}", exc_info=True)
            return Response({"error": "Invalid response from Zoho Books when fetching organizations."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ZohoBooksSetExternalOrganizationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, integration_id, *args, **kwargs):
        try:
            integration = Integration.objects.get(
                id=integration_id,
                organization=request.user.organization,
                provider=Integration.Provider.ZOHOBOOKS
            )
        except Integration.DoesNotExist:
            return Response({"error": "Integration not found or access denied."}, status=status.HTTP_404_NOT_FOUND)

        if integration.connection_status != Integration.Status.PENDING_EXTERNAL_ID:
            if integration.connection_status == Integration.Status.CONNECTED and integration.external_id:
                 return Response({"error": "This integration is already configured with an external organization."}, status=status.HTTP_400_BAD_REQUEST)
            # Add check for NEEDS_REAUTH
            if integration.connection_status == Integration.Status.NEEDS_REAUTH:
                return Response(
                    {"error": "reauthorization_required", 
                     "detail": "Connection to Zoho Books requires re-authorization before selecting an organization.",
                     "provider": "zohobooks",
                     "integration_id": integration.id
                     },
                    status=status.HTTP_401_UNAUTHORIZED
                )
            return Response({"error": "Integration is not awaiting external organization selection."}, status=status.HTTP_400_BAD_REQUEST)

        external_org_id = request.data.get('external_organization_id')
        external_org_name = request.data.get('external_organization_name', 'Zoho Books Connection')

        if not external_org_id:
            return Response({"error": "external_organization_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Check for uniqueness: an organization cannot have two integrations for the same provider and same external_id
        if Integration.objects.filter(
            organization=integration.organization,
            provider=integration.provider,
            external_id=external_org_id
        ).exclude(id=integration.id).exists():
            return Response({"error": "This Zoho Books organization is already connected to your FinSync organization."}, 
                            status=status.HTTP_409_CONFLICT)
        
        try:
            integration.external_id = external_org_id
            integration.name = external_org_name if external_org_name else f"Zoho Books - {external_org_id}"
            integration.connection_status = Integration.Status.CONNECTED
            integration.last_successful_sync = timezone.now() # Mark as successful configuration
            integration.last_sync_error = None
            integration.save(update_fields=['external_id', 'name', 'connection_status', 'last_successful_sync', 'last_sync_error'])
            logger.info(f"Successfully set external organization ID {external_org_id} for integration {integration.id}.")
            return Response({"message": "Zoho Books external organization configured successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error updating integration {integration.id} with external_id: {e}", exc_info=True)
            return Response({"error": "Failed to save external organization configuration."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 