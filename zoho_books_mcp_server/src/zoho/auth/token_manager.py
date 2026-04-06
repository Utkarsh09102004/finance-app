import os
import requests
import json
import webbrowser
from urllib.parse import urlencode
from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time
from typing import Dict, Optional
from datetime import datetime, timedelta

# Simple HTTP server to capture the authorization code
class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse the query parameters to extract the authorization code
        import urllib.parse
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        # Extract code and location
        if 'code' in params:
            self.server.authorization_code = params['code'][0]
            location = params.get('location', [''])[0]
            accounts_server = params.get('accounts-server', ['https://accounts.zoho.in'])[0]
            self.server.location = location
            self.server.accounts_server = accounts_server
            
            # Send a response to the browser
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            response = f"""
            <html>
            <body>
                <h1>Authorization Successful!</h1>
                <p>You can close this window now and return to the application.</p>
                <p>Code: {self.server.authorization_code}</p>
                <p>Location: {location}</p>
            </body>
            </html>
            """
            self.wfile.write(response.encode())
            
            # Signal that we've received the code
            self.server.code_received = True
        else:
            # Handle error case
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Error: No authorization code received</h1></body></html>')

    def log_message(self, format, *args):
        # Suppress log messages
        return

def start_callback_server(port=8000):
    server = HTTPServer(('localhost', port), CallbackHandler)
    server.authorization_code = None
    server.location = ''
    server.accounts_server = ''
    server.code_received = False
    
    # Run the server in a separate thread
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    return server

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Get credentials from environment variables
    client_id = os.getenv("ZOHO_CLIENT_ID")
    redirect_url = os.getenv("ZOHO_REDIRECT_URL")
    
    print(f"Starting OAuth flow with client ID: {client_id}")
    print(f"Redirect URL: {redirect_url}")
    
    # Start the callback server
    callback_server = start_callback_server(port=8000)
    
    # STEP 1: Get Authorization Code
    # Prepare OAuth parameters for authorization request
    auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "scope": "ZohoBooks.fullaccess.all",  # Adjust scope as needed
        "redirect_uri": redirect_url,
        "access_type": "offline",  # To get a refresh token
        "prompt": "consent"  # Force consent screen
    }
    
    # Construct the authorization URL
    base_auth_url = "https://accounts.zoho.in/oauth/v2/auth"
    auth_url = f"{base_auth_url}?{urlencode(auth_params)}"
    
    print(f"Opening browser for authorization at: {auth_url}")
    
    # Open the authorization URL in the default browser
    webbrowser.open(auth_url)
    
    # Wait for the callback to receive the authorization code
    print("Waiting for authorization code...")
    timeout = 300  # 5 minutes timeout
    start_time = time.time()
    
    while not callback_server.code_received and time.time() - start_time < timeout:
        time.sleep(1)
    
    if not callback_server.code_received:
        print("Timed out waiting for authorization code.")
        callback_server.shutdown()
        return
    
    # Get the authorization code from the callback server
    authorization_code = callback_server.authorization_code
    location = callback_server.location
    accounts_server = callback_server.accounts_server
    
    print(f"Authorization code received: {authorization_code}")
    print(f"User location: {location}")
    
    # Determine the correct accounts server based on location
    token_base_url = accounts_server if accounts_server else "https://accounts.zoho.in"
    
    # STEP 2: Exchange Authorization Code for Access Token
    # Now that we have the authorization code, exchange it for an access token
    token_endpoint = f"{token_base_url}/oauth/v2/token"
    
    # Prepare token request parameters
    token_params = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": os.getenv("ZOHO_CLIENT_SECRET", ""),  # You need to add this to your .env file
        "code": authorization_code,
        "redirect_uri": redirect_url
    }
    
    print("Exchanging authorization code for access token...")
    
    # Make the token request
    token_response = requests.post(token_endpoint, data=token_params)
    
    # Check if the token request was successful
    if token_response.status_code == 200:
        token_data = token_response.json()
        print("Access token obtained successfully!")
        print(json.dumps(token_data, indent=2))
        
        # Save the tokens to a file for future use
        save_tokens(token_data)
        print("Tokens saved successfully!")
            
        # The token_data will contain:
        # - access_token: For making API calls
        # - refresh_token: For getting a new access token when it expires (if access_type=offline)
        # - expires_in: Expiration time in seconds
    else:
        print(f"Failed to obtain access token. Status code: {token_response.status_code}")
        print(f"Response: {token_response.text}")
    
    # Shutdown the callback server
    callback_server.shutdown()

def refresh_access_token(refresh_token: str, client_id: str, client_secret: str, accounts_server: str = "https://accounts.zoho.in") -> Optional[Dict]:
    """
    Refresh the Zoho access token using the refresh token.
    
    Args:
        refresh_token (str): The refresh token obtained during initial authorization
        client_id (str): Your Zoho client ID
        client_secret (str): Your Zoho client secret
        accounts_server (str): The Zoho accounts server URL (varies by data center)
        
    Returns:
        dict: New token information including access_token and expires_in
        None: If the refresh failed
    """
    # Prepare the refresh token request parameters
    refresh_params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    # Construct the token endpoint URL
    token_endpoint = f"{accounts_server}/oauth/v2/token"
    
    try:
        # Make the refresh token request
        response = requests.post(token_endpoint, data=refresh_params)
        
        # Check if the request was successful
        if response.status_code == 200:
            token_data = response.json()
            
            # Add refresh time information
            token_data['refresh_time'] = datetime.now().isoformat()
            token_data['expires_at'] = (datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600))).isoformat()
            
            # Save the updated tokens
            save_tokens(token_data)
            
            print("Access token refreshed successfully!")
            return token_data
        else:
            print(f"Failed to refresh access token. Status code: {response.status_code}")
            print(f"Error response: {response.text}")
            return None
            
    except Exception as e:
        print(f"Error refreshing access token: {str(e)}")
        return None

def get_token_file_path():
    """Get the path to the token file in the zoho_books_mcp_server directory"""
    current_file = os.path.abspath(__file__)
    auth_dir = os.path.dirname(current_file)
    zoho_dir = os.path.dirname(auth_dir)
    src_dir = os.path.dirname(zoho_dir)
    server_root = os.path.dirname(src_dir)
    return os.path.join(server_root, "zoho_tokens.json")

def save_tokens(token_data: Dict, filename: str = None) -> None:
    """
    Save token information to a JSON file.
    
    Args:
        token_data (dict): Token information to save
        filename (str): Name of the file to save tokens to (deprecated, will use default location)
    """
    try:
        token_path = get_token_file_path()
        
        # If file exists, read existing data first
        existing_data = {}
        if os.path.exists(token_path):
            with open(token_path, 'r') as f:
                existing_data = json.load(f)
        
        # Update existing data with new token data
        existing_data.update(token_data)
        
        # Save updated data
        with open(token_path, 'w') as f:
            json.dump(existing_data, f, indent=2)
            
        print(f"Tokens saved to {token_path}")
    except Exception as e:
        print(f"Error saving tokens: {str(e)}")

def get_valid_access_token() -> Optional[str]:
    """
    Get a valid access token, refreshing if necessary.
    
    Returns:
        str: Valid access token
        None: If unable to get a valid token
    """
    try:
        # Load environment variables
        load_dotenv()
        
        # Get token file path
        token_path = get_token_file_path()
        
        # Load saved tokens
        with open(token_path, 'r') as f:
            token_data = json.load(f)
        
        # Check if token is expired
        expires_at = datetime.fromisoformat(token_data.get('expires_at', '2000-01-01'))
        
        # If token is expired or will expire in next 5 minutes, refresh it
        if datetime.now() + timedelta(minutes=5) >= expires_at:
            print("Access token expired or will expire soon. Refreshing...")
            
            # Get credentials from environment
            client_id = os.getenv("ZOHO_CLIENT_ID")
            client_secret = os.getenv("ZOHO_CLIENT_SECRET")
            
            # Get the refresh token from saved data
            refresh_token = token_data.get('refresh_token')
            
            if not all([client_id, client_secret, refresh_token]):
                print("Missing required credentials for token refresh")
                return None
            
            # Refresh the token
            new_token_data = refresh_access_token(
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                accounts_server=token_data.get('accounts_server', 'https://accounts.zoho.in')
            )
            print(new_token_data)
            
            if new_token_data:
                return new_token_data.get('access_token')
            return None
            
        # If token is still valid, return it
        return token_data.get('access_token')
        
    except FileNotFoundError:
        print("No saved tokens found. Please authenticate first.")
        return None
    except Exception as e:
        print(f"Error getting valid access token: {str(e)}")
        return None

if __name__ == "__main__":

    main()

    # load_dotenv()
    
    # client_id = os.getenv("ZOHO_CLIENT_ID")
    # client_secret = os.getenv("ZOHO_CLIENT_SECRET")
    
    # try:
    #     # Try to read existing tokens
    #     with open("zoho_tokens.json", 'r') as f:
    #         saved_tokens = json.load(f)
    #         refresh_token = saved_tokens.get('refresh_token')
            
    #         if refresh_token:
    #             print("Refreshing access token...")
    #             new_token_data = refresh_access_token(
    #                 refresh_token=refresh_token,
    #                 client_id=client_id,
    #                 client_secret=client_secret
    #             )
                
    #             if new_token_data:
    #                 print("New access token details:")
    #                 print(json.dumps(new_token_data, indent=2))
                    
    #                 # Example of getting a valid token
    #                 print("\nTesting get_valid_access_token function...")
    #                 valid_token = get_valid_access_token()
    #                 if valid_token:
    #                     print(f"Valid access token obtained: {valid_token[:10]}...")
    #         else:
    #             print("No refresh token found in saved tokens.")
                
    # except FileNotFoundError:
    #     print("No saved tokens found. Please run the authorization flow first.")
    # except Exception as e:
    #     print(f"Error: {str(e)}")