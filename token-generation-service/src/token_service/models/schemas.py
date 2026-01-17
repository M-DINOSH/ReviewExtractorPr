"""
Pydantic schemas for API requests and responses
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ========== Client Schemas ==========

class ClientWithBranchCreate(BaseModel):
    """Schema for creating a client with workspace info in single request"""
    client_id: str = Field(..., min_length=1, max_length=255, description="Google OAuth Client ID")
    client_secret: str = Field(..., min_length=1, max_length=512, description="Google OAuth Client Secret")
    redirect_uri: str = Field(..., description="OAuth redirect URI")
    branch_id: str = Field(..., min_length=1, max_length=255, description="Unique branch identifier (UUID)")
    workspace_email: str = Field(..., max_length=255, description="Workspace email manager")
    workspace_name: str = Field(..., max_length=255, description="Workspace/Branch name")


class ClientBranchResponse(BaseModel):
    """Schema for client + workspace creation response"""
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


# ========== Token Schemas ==========

class TokenRefreshRequest(BaseModel):
    """Schema for token refresh request"""
    client_id: int = Field(..., description="Client database ID")


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


# ========== OAuth Schemas ==========

class OAuthCallbackResponse(BaseModel):
    """Schema for OAuth callback response"""
    success: bool
    message: str
    client_id: Optional[str] = None
    branch_id: Optional[str] = None
    access_token: Optional[str] = None
    expires_at: Optional[datetime] = None


# ========== General Schemas ==========

class HealthCheckResponse(BaseModel):
    """Schema for health check response"""
    status: str = "healthy"
    service: str = "Token Generation Service"
    version: str = "1.0.0"
    timestamp: datetime
    database: str = "connected"
