from pydantic import BaseModel
from typing import Optional, Dict

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

class CreatePlaylistRequest(BaseModel):
    """Request model for creating a playlist"""
    name: str
    description: Optional[str] = None
    public: bool = True

class PlaylistResponse(BaseModel):
    """Response model for playlist data"""
    id: str
    name: str
    description: Optional[str] = None
    external_urls: Dict[str, str]
    images: list
    owner: Dict
    public: bool
    tracks: Dict
    uri: str
    
    class Config:
        from_attributes = True

class ChatMessage(BaseModel):
    """Single chat message"""
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    messages: list[ChatMessage]
    system: Optional[str] = None

class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    message: str
