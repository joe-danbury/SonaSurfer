from pydantic import BaseModel
from typing import Optional

class SpotifyTokenResponse(BaseModel):
    """Response from Spotify token endpoint"""
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"
    scope: Optional[str] = None

class SpotifyAuthResponse(BaseModel):
    """Response sent to frontend after OAuth callback"""
    access_token: str
    refresh_token: str
    expires_at: int  # Unix timestamp when token expires

class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    message: Optional[str] = None
