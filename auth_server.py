import os
import json
import time
import threading
import logging
import logging.handlers
from flask import Flask, jsonify
from authlib.integrations.requests_client import OAuth2Session
from urllib.parse import urlparse, parse_qs
from config import SCHWAB_CLIENT_ID, SCHWAB_CLIENT_SECRET, SCHWAB_AUTHORIZE_URL, SCHWAB_TOKEN_URL, REDIRECT_URI

TOKEN_FILE = "token_store.json"

app = Flask(__name__)

oauth_session = OAuth2Session(
    client_id=SCHWAB_CLIENT_ID,
    client_secret=SCHWAB_CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
)

current_token = {}

def save_token(token):
    """
    Save the token to disk and update the global `current_token`.

    Args:
        token (dict): The token dictionary containing access and refresh tokens, expiration time, etc.
    """
    global current_token
    token['expires_at'] = time.time() + token.get('expires_in', 3600)
    current_token = token
    with open(TOKEN_FILE, 'w') as f:
        json.dump(token, f)
    logging.info("Token saved to disk: {}".format(TOKEN_FILE))

def load_token():
    """
    Load the token from memory or disk.

    Returns:
        dict: The token dictionary if available, otherwise an empty dictionary.
    """
    global current_token
    if current_token:
        return current_token
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            current_token = json.load(f)
            logging.info("Token loaded from disk.")
    return current_token

def perform_initial_auth():
    """
    Perform the initial OAuth2 authorization flow to obtain an access token.

    This function prompts the user to visit an authorization URL and paste the redirect URL
    after completing the authorization process.
    """
    uri, state = oauth_session.create_authorization_url(SCHWAB_AUTHORIZE_URL)
    print("\nStep 1: Visit this URL to authorize:")
    print(uri)
    redirected_url = input("\nStep 2: Paste the full redirect URL here: ").strip()
    parsed = urlparse(redirected_url)
    code = parse_qs(parsed.query).get("code")
    if not code:
        raise Exception("Missing authorization code.")
    token = oauth_session.fetch_token(
        url=SCHWAB_TOKEN_URL,
        authorization_response=redirected_url,
        client_secret=SCHWAB_CLIENT_SECRET
    )
    save_token(token)
    print("Authorization successful.")

def refresh_token():
    """
    Refresh the access token using the refresh token.

    Returns:
        dict: The new token dictionary.

    Raises:
        Exception: If no refresh token is available or the refresh process fails.
    """
    token = load_token()
    if not token.get("refresh_token"):
        raise Exception("No refresh token available.")
    new_session = OAuth2Session(
        client_id=SCHWAB_CLIENT_ID,
        client_secret=SCHWAB_CLIENT_SECRET
    )
    new_token = new_session.refresh_token(
        SCHWAB_TOKEN_URL,
        refresh_token=token['refresh_token']
    )
    save_token(new_token)
    logging.info("Token refreshed successfully.")
    return new_token

def auto_refresh_loop():
    """
    Continuously monitor the token's expiration and refresh it when necessary.

    This function runs in a separate thread to ensure the token remains valid.
    """
    while True:
        try:
            token = load_token()
            if 'expires_at' in token and time.time() >= token['expires_at'] - 60:
                logging.info("Token is about to expire. Refreshing...")
                refresh_token()
        except Exception as e:
            logging.error(f"Auto-refresh error: {e}")
        time.sleep(30)

def serve_headless():
    """
    Start the Flask server to serve token-related endpoints.

    This function also starts the auto-refresh loop in a separate thread.
    """
    app = Flask(__name__)

    @app.route('/get_token')
    def get_token():
        """
        Serve the current access token via the `/get_token` endpoint.

        Returns:
            Response: A JSON response containing the access token and its metadata.
        """
        from flask import request
        requester_ip = request.remote_addr
        try:
            token = load_token()
            if 'expires_at' in token and time.time() >= token['expires_at']:
                logging.info("Token expired. Refreshing...")
                token = refresh_token()
            logging.info(f"Access token served via /get_token to IP: {requester_ip}")
            return jsonify({
                "access_token": token.get('access_token', ''),
                "expires_at": token.get('expires_at'),
                "expires_in": int(token['expires_at'] - time.time()) if 'expires_at' in token else None,
                "should_refresh_in": max(int(token['expires_at'] - time.time() - 60), 0) if 'expires_at' in token else None
            })
        except Exception as e:
            logging.error(f"Error serving token to {requester_ip}: {e}")
            return jsonify({"error": "Failed to retrieve token"}), 500

    t = threading.Thread(target=auto_refresh_loop)
    t.daemon = True
    t.start()
    app.run(port=5001, debug=False)

def initialize_logging():
    """
    Initialize the logging configuration for the application.
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(),
            logging.handlers.RotatingFileHandler(
                "token_server.log", maxBytes=5 * 1024 * 1024, backupCount=3
            )
        ]
    )
    logging.info("Logging initialized.")

def handle_fatal_error(e):
    """
    Handle fatal errors by printing the traceback to the console.

    Args:
        e (Exception): The exception that caused the fatal error.
    """
    import traceback
    print("Fatal error occurred:")
    print(traceback.format_exc())

if __name__ == '__main__':
    try:
        # Check if the token file exists and validate the token
        if not os.path.exists(TOKEN_FILE):
            print("Token file not found. Performing initial authentication.")
            perform_initial_auth()
        else:
            print("Token file found. Validating token...")
            token = load_token()
            if 'expires_at' not in token or time.time() >= token['expires_at']:
                print("Token is expired or invalid. Attempting to refresh...")
                try:
                    refresh_token()
                except Exception as e:
                    print(f"Token refresh failed: {e}")
                    print("Falling back to initial authentication.")
                    perform_initial_auth()
            else:
                print("Token is valid. Proceeding with server startup.")

        # Initialize logging after the workflow
        initialize_logging()

        # Start the headless server
        serve_headless()
    except Exception as e:
        handle_fatal_error(e)