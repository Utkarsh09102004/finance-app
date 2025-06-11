import logging

logger = logging.getLogger(__name__)

class OAuthSessionMiddleware:
    """
    Middleware to help with OAuth session state persistence.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Check if this is a callback from an OAuth provider
        if request.path.endswith('/callback/') and 'state' in request.GET:
            state = request.GET.get('state')
            logger.info(f"OAuth callback detected with state: {state}")
            
            # Restore the OAuth state in the session
            # This helps with session persistence issues across redirects
            request.session['zohobooks_oauth_state'] = state
            
        return self.get_response(request) 