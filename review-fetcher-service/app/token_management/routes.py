"""
Token Management API Routes
These routes handle OAuth flow and token management
"""
import uuid
import urllib.parse
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.token_management.database import get_db
from app.token_management.models import (
    Client,
    Token,
    ClientWithBranchCreate, ClientBranchResponse,
    OAuthCallbackResponse,
    TokenRefreshRequest, TokenRefreshResponse,
)
from app.token_management.services import (
    client_service,
    token_service,
    oauth_service,
)
import structlog

logger = structlog.get_logger()

# Create router for token management
token_router = APIRouter(prefix="/token-management", tags=["Token Management"])

# Google OAuth Configuration
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_SCOPE = "https://www.googleapis.com/auth/business.manage"


# ========== Client Management ==========

@token_router.post("/clients", response_model=ClientBranchResponse, status_code=201)
def create_client(client_data: ClientWithBranchCreate, db: Session = Depends(get_db)):
    """
    Register a new OAuth client with workspace info
    
    - **client_id**: Google OAuth Client ID
    - **client_secret**: Google OAuth Client Secret
    - **redirect_uri**: OAuth redirect URI
    - **branch_id**: Unique branch identifier (UUID)
    - **workspace_email**: Email manager for workspace
    - **workspace_name**: Name of workspace/branch
    """
    # Check if client already exists
    existing_client = client_service.get_client_by_client_id(db, client_data.client_id)
    if existing_client:
        raise HTTPException(status_code=400, detail="Client already registered")
    
    # Check if branch_id already exists
    existing_branch = db.query(Client).filter(Client.branch_id == client_data.branch_id).first()
    if existing_branch:
        raise HTTPException(status_code=400, detail="Branch ID already exists")
    
    try:
        client = Client(
            client_id=client_data.client_id,
            client_secret=client_data.client_secret,
            redirect_uri=client_data.redirect_uri,
            branch_id=client_data.branch_id,
            workspace_email=client_data.workspace_email,
            workspace_name=client_data.workspace_name,
        )
        db.add(client)
        db.commit()
        db.refresh(client)
        
        return ClientBranchResponse(
            success=True,
            message="Client created successfully",
            client_id=client.id,
            client_oauth_id=client.client_id,
            branch_id=client.id,
            branch_identifier=client.branch_id,
            email=client.workspace_email,
            workspace_name=client.workspace_name,
            redirect_uri=client.redirect_uri,
            created_at=client.created_at,
        )
    except Exception as e:
        logger.error("create_client_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create client: {str(e)}")


# ========== OAuth Flow ==========

@token_router.get("/oauth/login/{client_id}")
def oauth_login_redirect(client_id: int, db: Session = Depends(get_db)):
    """
    Browser redirect endpoint to start OAuth flow
    
    Redirects directly to Google OAuth consent screen.
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client or not client.is_active:
        return JSONResponse(
            status_code=404,
            content={"error": "Client not found or inactive"}
        )
    
    # Build and redirect to authorization URL
    auth_url = (
        f"{GOOGLE_AUTH_URL}"
        f"?client_id={client.client_id}"
        f"&redirect_uri={urllib.parse.quote(client.redirect_uri, safe=':/?=&')}"
        f"&response_type=code"
        f"&scope={urllib.parse.quote(GOOGLE_SCOPE, safe='/:')}"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    
    logger.info("oauth_login_redirect", client_id=client.id)
    
    return RedirectResponse(auth_url)


@token_router.get("/auth/callback", response_model=OAuthCallbackResponse)
async def oauth_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    OAuth callback endpoint
    
    Google redirects here after user authorization.
    Exchanges authorization code for access and refresh tokens.
    """
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    
    # Check for Google OAuth errors
    if error:
        logger.error("oauth_error_from_google", error=error)
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")
    
    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")
    
    # Find client by matching redirect_uri from request
    client = None
    for c in db.query(Client).all():
        if c.redirect_uri in str(request.url):
            client = c
            break

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    try:
        # Exchange code for tokens
        token_data = await oauth_service.exchange_code_for_token(
            code=code,
            client_id=client.client_id,
            client_secret=client.client_secret,
            redirect_uri=client.redirect_uri,
        )
        
        # Store tokens in database
        token = token_service.create_token(
            db=db,
            client_id=client.id,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data.get("expires_in"),
            token_type=token_data.get("token_type", "Bearer"),
            scope=token_data.get("scope"),
        )
        
        logger.info("oauth_callback_successful", client_id=client.id)
        
        return OAuthCallbackResponse(
            success=True,
            message="OAuth flow completed successfully",
            client_id=client.client_id,
            branch_id=client.branch_id,
            access_token=token.access_token,
            expires_at=token.expires_at,
        )
        
    except Exception as e:
        logger.error("oauth_callback_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to exchange code for token: {str(e)}")


# ========== Token Operations ==========

@token_router.post("/tokens/refresh", response_model=TokenRefreshResponse)
async def refresh_access_token(
    request: TokenRefreshRequest,
    db: Session = Depends(get_db),
):
    """
    Refresh access token using refresh token
    When access token expires, use this endpoint with refresh token to get a new access token.
    """
    client = db.query(Client).filter(Client.id == request.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    token = db.query(Token).filter(
        Token.client_id == client.id,
        Token.is_valid == True,
    ).first()
    
    if not token:
        raise HTTPException(status_code=404, detail="No valid token found for client")
    
    if not token.refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token available. Please complete OAuth flow again.")
    
    try:
        new_token_data = await oauth_service.refresh_access_token(
            refresh_token=token.refresh_token,
            client_id=client.client_id,
            client_secret=client.client_secret,
        )
        
        token.access_token = new_token_data["access_token"]
        token.token_type = new_token_data.get("token_type", "Bearer")
        token.scope = new_token_data.get("scope", token.scope)
        token.last_refreshed_at = datetime.utcnow()
        
        if new_token_data.get("expires_in"):
            token.expires_at = datetime.utcnow() + timedelta(seconds=new_token_data["expires_in"])
        
        if new_token_data.get("refresh_token"):
            token.refresh_token = new_token_data["refresh_token"]
        
        db.commit()
        db.refresh(token)
        
        logger.info("token_refreshed", client_id=client.id)
        
        return TokenRefreshResponse(
            success=True,
            message="Token refreshed successfully",
            client_id=client.id,
            branch_id=client.branch_id,
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_at=token.expires_at,
            token_type=token.token_type,
        )
        
    except Exception as e:
        logger.error("token_refresh_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to refresh token: {str(e)}")


@token_router.get("/tokens/{branch_id}", response_model=TokenRefreshResponse)
async def get_token_by_branch(
    branch_id: str,
    db: Session = Depends(get_db),
):
    """
    Get current valid access token for a branch
    
    Review Fetcher Service calls this to get the access token for making API requests.
    If token is expiring soon, automatically refreshes it.
    
    - **branch_id**: Branch identifier from client registration
    """
    client = db.query(Client).filter(Client.branch_id == branch_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client/Branch not found")
    
    try:
        # This will auto-refresh if token is expiring soon
        token = await token_service.ensure_valid_token(db, client)
        
        return TokenRefreshResponse(
            success=True,
            message="Token retrieved successfully",
            client_id=client.id,
            branch_id=client.branch_id,
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_at=token.expires_at,
            token_type=token.token_type,
        )
        
    except Exception as e:
        logger.error("get_token_failed", branch_id=branch_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get token: {str(e)}")
