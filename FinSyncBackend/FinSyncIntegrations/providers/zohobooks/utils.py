import logging
import requests
from django.conf import settings
from django.utils import timezone

# Forward declaration for type hinting if Integration is in models.py of the same app level
# from FinSyncIntegrations.models import Integration # This would be a circular import if utils is imported by models
# Instead, we'll use a string literal for type hinting if necessary or pass Integration as an argument with explicit type.

logger = logging.getLogger(__name__)

# Moved from views.py
def refresh_zoho_token(integration) -> bool:
    """
    Attempts to refresh the Zoho access token for the given integration.
    Updates the integration record with new tokens and status.
    Returns True if refresh was successful, False otherwise.
    
    integration: An instance of the Integration model.
    """
    # Explicitly import Integration here if not using forward declaration or string type hints
    # This is often safer to avoid import issues during Django startup.
    from FinSyncIntegrations.models import Integration # Placed here to avoid potential circular imports at module level

    if not integration.get_refresh_token():
        logger.warning(f"No refresh token available for integration {integration.id} ({integration.organization.name})")
        integration.connection_status = Integration.Status.NEEDS_REAUTH
        integration.last_sync_error = "Refresh token is missing. Re-authorization required."
        integration.save(update_fields=['connection_status', 'last_sync_error'])
        return False

    payload = {
        'client_id': settings.ZOHO_CLIENT_ID,
        'client_secret': settings.ZOHO_CLIENT_SECRET,
        'refresh_token': integration.get_refresh_token(),
        'grant_type': 'refresh_token',
    }
    response = None # Initialize response to None
    try:
        logger.info(f"Attempting to refresh token for integration {integration.id} ({integration.organization.name})")
        response = requests.post(settings.ZOHO_TOKEN_URL, data=payload, timeout=15) # Increased timeout slightly
        response.raise_for_status()
        token_data = response.json()

        new_access_token = token_data.get('access_token')
        new_expires_in = token_data.get('expires_in')  # Seconds
        # Zoho typically does not return a new refresh token with a refresh grant.
        # If it did, you would capture it: new_refresh_token = token_data.get('refresh_token')

        if not new_access_token:
            logger.error(f"Refresh token did not return a new access token for integration {integration.id}. Zoho response: {token_data}")
            integration.connection_status = Integration.Status.NEEDS_REAUTH
            integration.last_sync_error = "Failed to get new access token during refresh. Re-authorization may be required."
            integration.save(update_fields=['connection_status', 'last_sync_error'])
            return False
        
        # Determine original status before refresh, to set it back if it was PENDING_EXTERNAL_ID
        original_status_before_potential_error = integration.connection_status
        if original_status_before_potential_error == Integration.Status.NEEDS_REAUTH:
             # If it was NEEDS_REAUTH and we are successfully refreshing, it should become CONNECTED or PENDING
             current_status_after_refresh = Integration.Status.PENDING_EXTERNAL_ID if not integration.external_id else Integration.Status.CONNECTED
        else:
            current_status_after_refresh = original_status_before_potential_error

        integration.set_tokens(new_access_token, integration.get_refresh_token(), new_expires_in) # Use existing refresh token
        integration.connection_status = current_status_after_refresh 
        integration.last_sync_error = None
        integration.save(update_fields=['access_token_encrypted', 'token_expiry', 'connection_status', 'last_sync_error'])
        logger.info(f"Successfully refreshed token for integration {integration.id} ({integration.organization.name}). Status set to {integration.connection_status}.")
        return True

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTPError during token refresh for integration {integration.id}: {e}. Response: {response.text if response else 'No response'}", exc_info=True)
        error_code = "unknown_http_error"
        if response is not None:
            try:
                error_data = response.json()
                error_code = error_data.get("error", error_code)
                if error_code in ["invalid_grant", "invalid_client", "unauthorized_client"]:
                    integration.connection_status = Integration.Status.NEEDS_REAUTH
                    integration.last_sync_error = f"Refresh token invalid or revoked ({error_code}). Re-authorization required."
                else:
                    integration.connection_status = Integration.Status.ERROR # Or keep current status
                    integration.last_sync_error = f"Token refresh HTTP error ({response.status_code}): {error_code}"
            except ValueError: # Not JSON
                integration.connection_status = Integration.Status.ERROR
                integration.last_sync_error = f"Token refresh HTTP error ({response.status_code}): {response.text[:100]}"
        else:
            integration.connection_status = Integration.Status.ERROR
            integration.last_sync_error = f"Token refresh request failed with HTTPError and no response object: {e}"
        integration.save(update_fields=['connection_status', 'last_sync_error'])
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"RequestException during token refresh for integration {integration.id}: {e}", exc_info=True)
        integration.connection_status = Integration.Status.ERROR # Or keep current status
        integration.last_sync_error = f"Token refresh request failed: {str(e)[:100]}"
        integration.save(update_fields=['connection_status', 'last_sync_error'])
        return False

def get_valid_access_token(integration) -> str | None:
    """
    Retrieves a valid access token for the integration, refreshing it if necessary.
    
    integration: An instance of the Integration model.
    Returns the access token string or None if a valid token cannot be obtained.
    """
    # Explicitly import Integration here if not using forward declaration or string type hints
    from FinSyncIntegrations.models import Integration # Placed here to avoid potential circular imports
    
    if integration.connection_status == Integration.Status.NEEDS_REAUTH:
        logger.warning(f"Integration {integration.id} requires re-authentication. Cannot get access token.")
        return None
    
    if integration.connection_status == Integration.Status.DISCONNECTED:
        logger.warning(f"Integration {integration.id} is disconnected. Cannot get access token.")
        return None

    current_access_token = integration.get_access_token() # This gets the raw (but encrypted) token

    # Check if token is missing or expired/nearing expiry
    # Add a small buffer (e.g., 5 minutes) to the expiry check
    refresh_needed = False
    if not current_access_token:
        logger.info(f"No current access token for integration {integration.id}. Refresh might be needed or initial auth incomplete.")
        # If there's no access token at all, but we have a refresh token, try refreshing.
        # This could happen if an initial token fetch failed but refresh token was stored.
        if integration.get_refresh_token():
             refresh_needed = True
        else: # No access token and no refresh token
            logger.warning(f"Integration {integration.id} has no access token and no refresh token.")
            if integration.connection_status not in [Integration.Status.PENDING_EXTERNAL_ID, Integration.Status.NEEDS_REAUTH]:
                # If it's not pending setup or already marked for reauth, something is wrong
                integration.connection_status = Integration.Status.ERROR
                integration.last_sync_error = "Missing access and refresh tokens."
                integration.save(update_fields=['connection_status', 'last_sync_error'])
            return None

    if not refresh_needed and integration.token_expiry and integration.token_expiry < (timezone.now() + timezone.timedelta(minutes=5)):
        logger.info(f"Access token for integration {integration.id} is expired or nearing expiry. Attempting refresh.")
        refresh_needed = True
    
    if refresh_needed:
        if not refresh_zoho_token(integration): # This function now handles setting NEEDS_REAUTH if refresh token is bad
            logger.warning(f"Failed to refresh token for integration {integration.id}. Previous status: {integration.connection_status}")
            # refresh_zoho_token already updated the status, including to NEEDS_REAUTH if applicable.
            return None # Return None, view should check status if it needs to differentiate.
        # After successful refresh, get the new token
        current_access_token = integration.get_access_token()
        if not current_access_token:
            logger.error(f"Access token is still null after supposedly successful refresh for {integration.id}")
            return None # Should not happen if refresh_zoho_token returned True and set tokens

    # If, after all checks, status is NEEDS_REAUTH, token is unusable.
    if integration.connection_status == Integration.Status.NEEDS_REAUTH:
        logger.warning(f"Integration {integration.id} is in NEEDS_REAUTH state after token checks. Cannot use access token.")
        return None
        
    return current_access_token 