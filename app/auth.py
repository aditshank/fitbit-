import json
import urllib.parse
from datetime import datetime, timedelta
from jose import jwt
from fastapi import HTTPException, Request
from starlette.responses import RedirectResponse
import requests
from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, HEALTH_SCOPES, SESSION_SECRET_KEY

AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

def create_session_token(user_data: dict) -> str:
    payload = {
        "sub": user_data.get("id", user_data.get("sub", "")),
        "email": user_data.get("email", ""),
        "name": user_data.get("name", ""),
        "picture": user_data.get("picture", ""),
        "access_token": user_data.get("access_token", ""),
        "refresh_token": user_data.get("refresh_token", ""),
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, SESSION_SECRET_KEY, algorithm="HS256")

def decode_session_token(token: str) -> dict:
    try:
        return jwt.decode(token, SESSION_SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return None

def get_authorization_url(state: str) -> str:
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(HEALTH_SCOPES + ["openid", "email", "profile"]),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTHORIZATION_URL}?{urllib.parse.urlencode(params)}"

def exchange_code(code: str) -> dict:
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    resp = requests.post(TOKEN_URL, data=data)
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
    return resp.json()

def refresh_access_token(refresh_token: str) -> dict:
    data = {
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "grant_type": "refresh_token",
    }
    resp = requests.post(TOKEN_URL, data=data)
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to refresh token")
    return resp.json()

def get_user_info(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(USERINFO_URL, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to get user info")
    return resp.json()

def get_logged_in_user(request: Request) -> dict:
    token = request.cookies.get("session")
    if not token:
        return None
    return decode_session_token(token)
