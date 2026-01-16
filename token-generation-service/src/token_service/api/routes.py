"""
API Routes for Token Generation Service
"""
import uuid
import urllib.parse
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..core.logging import get_logger
from ..models.database import Client, Token
from ..models.schemas import (
    ClientWithBranchCreate, ClientBranchResponse,
    OAuthCallbackResponse,
    HealthCheckResponse,
    TokenRefreshRequest, TokenRefreshResponse,
)
from ..services.client_service import client_service
from ..services.token_service import token_service
from ..services.oauth_service import oauth_service

logger = get_logger(__name__)

router = APIRouter()


# ========== Health Check ==========

@router.get("/health", response_model=HealthCheckResponse, tags=["General"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        db_status = "disconnected"
    
    return HealthCheckResponse(
        status="healthy" if db_status == "connected" else "unhealthy",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        timestamp=datetime.utcnow(),
        database=db_status,
    )


# ========== Client Management ==========

@router.post("/clients", response_model=ClientBranchResponse, tags=["Clients"], status_code=201)
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
        # Create client with all request body fields
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
        logger.error(f"Failed to create client: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create client: {str(e)}")


# ========== OAuth Flow ==========

@router.get("/oauth/login/{client_id}", tags=["OAuth"])
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
        f"{settings.GOOGLE_AUTH_URL}"
        f"?client_id={client.client_id}"
        f"&redirect_uri={urllib.parse.quote(client.redirect_uri, safe=':/?=&')}"
        f"&response_type=code"
        f"&scope={urllib.parse.quote(settings.GOOGLE_SCOPE, safe='/:')}"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    
    logger.info(f"OAuth login redirect for client_id={client.id}")
    
    return RedirectResponse(auth_url)


@router.get("/auth/callback", response_model=OAuthCallbackResponse, tags=["OAuth"])
async def oauth_callback(request: Request, db: Session = Depends(get_db)):
    """
    OAuth callback endpoint
    
    Google redirects here after user authorization.
    Exchanges authorization code for access and refresh tokens.
    """
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    
    # Check for Google OAuth errors
    if error:
        logger.error(f"OAuth error from Google: {error}")
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")
    
    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")
    
    # Get client from redirect_uri (since we store it per client)
    redirect_uri = request.query_params.get("redirect_uri")
    
    # Find client by matching code handling
    # We'll need to identify the client - for now search by redirect_uri from request
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
        
        logger.info(f"OAuth callback successful for client_id={client.id}")
        
        return OAuthCallbackResponse(
            success=True,
            message="OAuth flow completed successfully",
            client_id=client.client_id,
            branch_id=client.branch_id,
            access_token=token.access_token,
            expires_at=token.expires_at,
        )
        
    except Exception as e:
        logger.error(f"OAuth callback failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to exchange code for token: {str(e)}")


# ========== Token Management ==========

@router.post("/tokens/refresh", response_model=TokenRefreshResponse, tags=["Tokens"])
async def refresh_access_token(request: TokenRefreshRequest, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token
    When access token expires, use this endpoint with refresh token to get a new access token.
    Returns the new access token along with updated expiry.
    
    - **client_id**: Client database ID
    """
    # Get client
    client = db.query(Client).filter(Client.id == request.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get current token
    token = db.query(Token).filter(
        Token.client_id == client.id,
        Token.is_valid == True,
    ).first()
    
    if not token:
        raise HTTPException(status_code=404, detail="No valid token found for client")
    
    if not token.refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token available. Please complete OAuth flow again.")
    
    try:
        # Refresh the token using Google API
        new_token_data = await oauth_service.refresh_access_token(
            refresh_token=token.refresh_token,
            client_id=client.client_id,
            client_secret=client.client_secret,
        )
        
        # Update token in database
        token.access_token = new_token_data["access_token"]
        token.token_type = new_token_data.get("token_type", "Bearer")
        token.scope = new_token_data.get("scope", token.scope)
        token.last_refreshed_at = datetime.utcnow()
        
        # Update expiry if provided
        if new_token_data.get("expires_in"):
            token.expires_at = datetime.utcnow() + timedelta(seconds=new_token_data["expires_in"])
        
        # Update refresh token if provided
        if new_token_data.get("refresh_token"):
            token.refresh_token = new_token_data["refresh_token"]
        
        db.commit()
        db.refresh(token)
        
        logger.info(f"Token refreshed successfully for client_id={client.id}")
        
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
        logger.error(f"Token refresh failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to refresh token: {str(e)}")


@router.get("/tokens/{branch_id}", response_model=TokenRefreshResponse, tags=["Tokens"])
async def get_token_by_branch(branch_id: str, db: Session = Depends(get_db)):
    """
    Get current valid access token for a branch
    
    Review Fetcher Service calls this to get the access token for making API requests.
    If token is expiring soon, automatically refreshes it.
    
    - **branch_id**: Branch identifier from client registration
    
    Response includes:
    - access_token: Current valid access token for Google Business Profile API
    - expires_at: When the token expires
    - branch_id: The requested branch ID
    - token_type: "Bearer"
    """
    # Get client by branch_id
    client = db.query(Client).filter(Client.branch_id == branch_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client/Branch not found")
    
    # Get current token
    token = db.query(Token).filter(
        Token.client_id == client.id,
        Token.is_valid == True,
    ).first()
    
    if not token:
        raise HTTPException(status_code=404, detail="No valid token found. Please complete OAuth flow first.")
    
    # Check if token is expiring soon (within 5 minutes)
    time_until_expiry = (token.expires_at - datetime.utcnow()).total_seconds()
    if time_until_expiry < 300:  # 5 minutes
        try:
            # Auto-refresh if expiring soon
            if not token.refresh_token:
                raise HTTPException(status_code=400, detail="Token expired. Please complete OAuth flow again.")
            
            new_token_data = await oauth_service.refresh_access_token(
                refresh_token=token.refresh_token,
                client_id=client.client_id,
                client_secret=client.client_secret,
            )
            
            # Update token
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
            
            logger.info(f"Token auto-refreshed for branch_id={branch_id}")
        except Exception as e:
            logger.error(f"Auto-refresh failed for branch_id={branch_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")
    
    return TokenRefreshResponse(
        success=True,
        message="Token retrieved successfully",
        client_id=client.id,
        branch_id=client.branch_id,
        access_token=token.access_token,
        refresh_token=None,  # Don't send refresh token to external services
        expires_at=token.expires_at,
        token_type=token.token_type,
    )
