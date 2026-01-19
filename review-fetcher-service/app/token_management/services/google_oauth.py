"""
Google OAuth Client Configuration
"""
import os
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
import google.oauth2.jwt
import httpx
import json
from datetime import datetime, timedelta

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_OAUTH_SETTINGS = {
    "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
    "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
}


async def exchange_code_for_token(
    code: str, client_id: str, client_secret: str, redirect_uri: str
) -> dict:
    """
    Exchange authorization code for access token and refresh token
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        return response.json()


async def refresh_access_token(
    refresh_token: str, client_id: str, client_secret: str
) -> dict:
    """
    Refresh access token using refresh token
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        return response.json()
