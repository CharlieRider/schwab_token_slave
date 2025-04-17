import os
import json
import time
import threading
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
    global current_token
    token['expires_at'] = time.time() + token.get('expires_in', 3600)
    current_token = token
    with open(TOKEN_FILE, 'w') as f:
        json.dump(token, f)

def load_token():
    global current_token
    if current_token:
        return current_token
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            current_token = json.load(f)
    return current_token

def perform_initial_auth():
    uri, state = oauth_session.create_authorization_url(SCHWAB_AUTHORIZE_URL)
    print("\nStep 1: Visit this URL to authorize:")
    print(uri)
    redirected_url = input("\nStep 2: Paste the full redirect URL here: ").strip()
    parsed = urlparse(redirected_url)
    code = parse_qs(parsed.query).get("code")
    if not code:
        raise Exception("Missing authorization code.")
    token = oauth_session.fetch_token(url=SCHWAB_TOKEN_URL,
                                      authorization_response=redirected_url,
                                      client_secret=SCHWAB_CLIENT_SECRET
    )
    save_token(token)
    print("Token acquired and saved.")

def refresh_token():
    token = load_token()
    if not token.get("refresh_token"):
        raise Exception("No refresh token available.")
    new_session = OAuth2Session(
        client_id=SCHWAB_CLIENT_ID,
        client_secret=SCHWAB_CLIENT_SECRET,
        scope="read_accounts read_positions"
    )
    new_token = new_session.refresh_token(
        SCHWAB_TOKEN_URL,
        refresh_token=token['refresh_token']
    )
    save_token(new_token)
    print("Token refreshed.")
    return new_token

def auto_refresh_loop():
    while True:
        try:
            token = load_token()
            if 'expires_at' in token and time.time() >= token['expires_at'] - 60:
                refresh_token()
        except Exception as e:
            print(f"Auto-refresh error: {e}")
        time.sleep(30)

def serve_headless():
    app = Flask(__name__)

    @app.route('/get_token')
    def get_token():
        token = load_token()
        if 'expires_at' in token and time.time() >= token['expires_at']:
            token = refresh_token()
        return jsonify({
            "access_token": token.get('access_token', ''),
            "expires_at": token.get('expires_at'),
            "expires_in": int(token['expires_at'] - time.time()) if 'expires_at' in token else None,
            "should_refresh_in": max(int(token['expires_at'] - time.time() - 60), 0) if 'expires_at' in token else None
        })
    
    t = threading.Thread(target=auto_refresh_loop)
    t.daemon = True
    t.start()
    app.run(port=5001, debug=False)

if __name__ == '__main__':
    if not os.path.exists(TOKEN_FILE):
        perform_initial_auth()
    serve_headless()
