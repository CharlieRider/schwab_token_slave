# 🛡️ Schwab Token Server

A headless Python server that manages OAuth2 authentication with the Charles Schwab API and securely serves access tokens to internal clients via HTTP.
Goal is to have client scripts running seperately have an endpoint to build the authentication for API calls. Only have to authenticate once and don't have to have some super filetree, just start the slave in the morning, auth in, vibe out. 
---

## 📦 Features

- Performs an initial OAuth2 authorization flow via a CLI prompt
- Automatically refreshes expired tokens in the background
- Exposes a simple HTTP endpoint (`/get_token`) for retrieving access tokens
- Logs key events to both console and file

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install flask authlib python-dotenv
```

### 2. Configure environment

Create a `.env` file with your Schwab credentials:

```dotenv
SCHWAB_CLIENT_ID=your_client_id
SCHWAB_CLIENT_SECRET=your_client_secret
```

### 3. Run the server

```bash
python token_server.py
```

You will be prompted to open a URL and complete Schwab's OAuth authorization. Paste the redirected URL back into the terminal to complete the flow.

---

## 🔐 Token Access

### `GET /get_token`

Returns a JSON payload:

```json
{
  "access_token": "...",
  "expires_at": 1744920000,
  "expires_in": 3599,
  "should_refresh_in": 3539
}
```

- `expires_in`: seconds until token expires
- `should_refresh_in`: seconds until proactive refresh

---

## 🔁 Auto Refresh

- A background thread checks every 30 seconds
- Automatically refreshes token when expiration is near

---

## 📁 Files

```text
token_server.py       # Main server logic
token_store.json      # Saved OAuth tokens
.token_server.log     # Logs
dotenv                # Schwab credentials
```

---

## 📊 Logging

Logs to both:
- `token_server.log`
- Console (stdout)

Events include:
- Authorization success
- Token refreshes
- Token access with client IP

---

## ⚠️ Security Notes

- This server is intended for local/internal use only
- Do not expose `/get_token` publicly without adding:
  - IP whitelisting
  - Authorization headers or secrets
  - HTTPS if accessed outside localhost
---



