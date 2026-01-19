"""
Pydantic schemas for Token Management API
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl, EmailStr


# ========== Client Schemas ==========

class ClientCreate(BaseModel):
    client_id: str
    client_secret: str
    redirect_uri: HttpUrl


class ClientWithBranchCreate(BaseModel):
    client_id: str
    client_secret: str
    redirect_uri: str
    branch_id: str
    workspace_email: EmailStr
    workspace_name: str


class ClientBranchResponse(BaseModel):
    success: bool
    message: str
    client_id: int
    client_oauth_id: str
    branch_id: int
    branch_identifier: str
    email: EmailStr
    workspace_name: str
    redirect_uri: str
    created_at: datetime


class ClientUpdate(BaseModel):
    client_secret: Optional[str] = None
    redirect_uri: Optional[HttpUrl] = None
    is_active: Optional[bool] = None


# ========== OAuth Schemas ==========

class OAuthCallbackResponse(BaseModel):
    success: bool
    message: str
    client_id: str
    branch_id: str
    access_token: str
    expires_at: Optional[datetime]


# ========== Token Schemas ==========

class TokenRefreshRequest(BaseModel):
    client_id: int


class TokenRefreshResponse(BaseModel):
    success: bool
    message: str
    client_id: int
    branch_id: str
    access_token: str
    refresh_token: Optional[str]
    expires_at: Optional[datetime]
    token_type: str


class TokenResponse(BaseModel):
    success: bool
    access_token: str
    expires_at: Optional[datetime]
    is_valid: bool
