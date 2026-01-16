"""
Pydantic schemas for API requests and responses
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


# ========== Client Schemas ==========

class ClientBase(BaseModel):
    """Base schema for client"""
    client_id: str = Field(..., min_length=1, max_length=255, description="Google OAuth Client ID")
    redirect_uri: str = Field(..., description="OAuth redirect URI")


class ClientCreate(ClientBase):
    """Schema for creating a new client"""
    client_secret: str = Field(..., min_length=1, max_length=512, description="Google OAuth Client Secret")


class ClientWithBranchCreate(ClientBase):
    """Schema for creating a client with branch in one request"""
    client_secret: str = Field(..., min_length=1, max_length=512, description="Google OAuth Client Secret")
    branch_id: str = Field(..., min_length=1, max_length=255, description="Unique branch identifier (UUID)")
    workspace_email: str = Field(..., max_length=255, description="Workspace email manager")
    workspace_name: str = Field(..., max_length=255, description="Workspace/Branch name")


class ClientUpdate(BaseModel):
    """Schema for updating client"""
    client_secret: Optional[str] = Field(None, max_length=512)
    redirect_uri: Optional[str] = None
    is_active: Optional[bool] = None


class ClientResponse(ClientBase):
    """Schema for client response"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ClientWithSecret(ClientResponse):
    """Schema for client response with secret (admin only)"""
    client_secret: str
    
    model_config = ConfigDict(from_attributes=True)


# ========== Branch Schemas ==========

class BranchBase(BaseModel):
    """Base schema for branch"""
    branch_id: str = Field(..., min_length=1, max_length=255, description="Unique branch identifier")
    branch_name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None


class BranchCreate(BranchBase):
    """Schema for creating a new branch"""
    client_id: int = Field(..., description="Associated client ID")
    account_id: Optional[str] = Field(None, max_length=255, description="Google Business Account ID")
    location_id: Optional[str] = Field(None, max_length=255, description="Google Business Location ID")


class BranchUpdate(BaseModel):
    """Schema for updating branch"""
    branch_name: Optional[str] = Field(None, max_length=255)
    account_id: Optional[str] = Field(None, max_length=255)
    location_id: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class BranchResponse(BranchBase):
    """Schema for branch response"""
    id: int
    client_id: int
    account_id: Optional[str]
    location_id: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ========== Token Schemas ==========

class TokenBase(BaseModel):
    """Base schema for token"""
    token_type: str = "Bearer"
    scope: Optional[str] = None


class TokenCreate(TokenBase):
    """Schema for creating/storing a new token"""
    client_id: int
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None  # Seconds until expiry


class TokenResponse(BaseModel):
    """Schema for token response"""
    id: int
    client_id: int
    access_token: str
    token_type: str
    scope: Optional[str]
    expires_at: Optional[datetime]
    is_valid: bool
    is_revoked: bool
    created_at: datetime
    updated_at: datetime
    last_refreshed_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class TokenValidationResponse(BaseModel):
    """Schema for token validation response"""
    is_valid: bool
    access_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    message: str


class TokenRefreshResponse(BaseModel):
    """Schema for token refresh response"""
    success: bool
    message: str
    client_id: int
    branch_id: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: datetime
    token_type: str = "Bearer"


class TokenRefreshRequest(BaseModel):
    """Schema for token refresh request"""
    client_id: int = Field(..., description="Client database ID")

    expires_at: Optional[datetime] = None
    message: str


# ========== OAuth Schemas ==========

class OAuthStartResponse(BaseModel):
    """Schema for OAuth start response"""
    auth_url: str = Field(..., description="Google OAuth authorization URL")
    state: str = Field(..., description="OAuth state parameter for security")


class OAuthCallbackResponse(BaseModel):
    """Schema for OAuth callback response"""
    success: bool
    message: str
    client_id: Optional[str] = None
    branch_id: Optional[str] = None
    access_token: Optional[str] = None
    expires_at: Optional[datetime] = None


class ClientBranchResponse(BaseModel):
    """Schema for client + branch creation response"""
    success: bool
    message: str
    client_id: int
    client_oauth_id: str
    branch_id: int
    branch_identifier: str
    email: str
    workspace_name: str
    redirect_uri: str
    created_at: datetime


class TokenRefreshRequest(BaseModel):
    """Schema for token refresh request"""
    client_internal_id: int = Field(..., description="Internal client database ID")


class TokenRefreshResponse(BaseModel):
    """Schema for token refresh response"""
    success: bool
    message: str
    access_token: Optional[str] = None
    expires_at: Optional[datetime] = None


# ========== General Schemas ==========

class HealthCheckResponse(BaseModel):
    """Schema for health check response"""
    status: str = "healthy"
    service: str = "token-generation-service"
    version: str = "1.0.0"
    timestamp: datetime
    database: str = "connected"


class ErrorResponse(BaseModel):
    """Schema for error response"""
    error: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
