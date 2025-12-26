from pydantic import BaseModel, HttpUrl
from typing import Optional


class ClientOAuthConfig(BaseModel):
    client_id: str
    client_secret: str
    redirect_uri: HttpUrl


class ReviewOut(BaseModel):
    review_id: str
    rating: str
    comment: Optional[str]
    reviewer_name: Optional[str]
    reviewer_email: Optional[str] = "not_provided_by_google"
    organization: str
    location: str
