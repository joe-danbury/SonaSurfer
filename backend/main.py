from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
import yaml
import time
import secrets
import os

from services.spotify_service import SpotifyService
from models.schemas import SpotifyAuthResponse, ErrorResponse, CreatePlaylistRequest

# Load environment variables - explicitly look in backend directory
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

# Load config
config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
with open(config_path) as f:
    config = yaml.safe_load(f)

app = FastAPI(title=config['app']['name'])

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=config['app']['cors_origins'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Spotify service (lazy initialization to avoid errors on startup if .env is missing)
spotify_service = None

def get_spotify_service():
    """Get or create Spotify service instance"""
    global spotify_service
    if spotify_service is None:
        spotify_service = SpotifyService()
    return spotify_service

# In-memory state storage (for CSRF protection)
# In production, use Redis or similar
state_store = {}

@app.get("/")
async def root():
    return {"message": "SonaSurfer API"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/auth/spotify")
async def spotify_login():
    """Redirect user to Spotify authorization page"""
    service = get_spotify_service()
    # Generate random state for CSRF protection
    state = secrets.token_urlsafe(32)
    state_store[state] = True
    
    # Get authorization URL
    auth_url = service.get_auth_url(state=state)
    return RedirectResponse(url=auth_url)

@app.get("/callback")
async def spotify_callback(
    code: str = Query(..., description="Authorization code from Spotify"),
    state: str = Query(None, description="State parameter for CSRF protection"),
    error: str = Query(None, description="Error from Spotify if user denied")
):
    """Handle Spotify OAuth callback"""
    # Check for errors from Spotify
    if error:
        # Redirect to frontend with error
        frontend_url = f"{config['app']['cors_origins'][0]}/callback?error={error}"
        return RedirectResponse(url=frontend_url)
    
    # Validate state (CSRF protection)
    if state and state not in state_store:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    # Clean up state
    if state:
        state_store.pop(state, None)
    
    try:
        # Exchange code for tokens
        service = get_spotify_service()
        token_data = service.exchange_code_for_token(code)
        
        # Calculate expires_at timestamp
        expires_at = int(time.time()) + token_data.get('expires_in', 3600)
        
        # Prepare response data
        response_data = {
            "access_token": token_data['access_token'],
            "refresh_token": token_data['refresh_token'],
            "expires_at": expires_at
        }
        
        # Redirect to frontend with tokens in URL fragment (more secure than query params)
        # Frontend will extract tokens from hash
        frontend_url = f"{config['app']['cors_origins'][0]}/callback#access_token={response_data['access_token']}&refresh_token={response_data['refresh_token']}&expires_at={response_data['expires_at']}"
        return RedirectResponse(url=frontend_url)
        
    except Exception as e:
        # Redirect to frontend with error
        frontend_url = f"{config['app']['cors_origins'][0]}/callback?error=token_exchange_failed&message={str(e)}"
        return RedirectResponse(url=frontend_url)

@app.post("/auth/refresh")
async def refresh_token(refresh_token: str = Query(..., description="Refresh token")):
    """Refresh an expired access token"""
    try:
        service = get_spotify_service()
        token_data = service.refresh_access_token(refresh_token)
        
        # Calculate new expires_at
        expires_at = int(time.time()) + token_data.get('expires_in', 3600)
        
        return SpotifyAuthResponse(
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token', refresh_token),  # Spotify may return new refresh token
            expires_at=expires_at
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to refresh token: {str(e)}")

@app.post("/playlists")
async def create_playlist(
    request: CreatePlaylistRequest,
    authorization: str = Header(..., description="Bearer token with access_token")
):
    """Create a new playlist for the authenticated user"""
    try:
        # Extract access token from Authorization header
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header. Expected 'Bearer <token>'")
        
        access_token = authorization.replace("Bearer ", "")
        
        # Create playlist
        service = get_spotify_service()
        playlist = service.create_playlist(
            access_token=access_token,
            name=request.name,
            description=request.description,
            public=request.public
        )
        
        return playlist
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create playlist: {str(e)}")

