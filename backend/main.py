from fastapi import FastAPI, HTTPException, Query, Header, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from dotenv import load_dotenv
import yaml
import time
import secrets
import os
import logging
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

from services.spotify_service import SpotifyService
from services.claude_service import ClaudeService
from services.extraction_service import ExtractionService
from models.schemas import SpotifyAuthResponse, ErrorResponse, CreatePlaylistRequest, ChatRequest, ChatResponse, AddTracksRequest
from typing import List, Dict

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

# Initialize services (lazy initialization to avoid errors on startup if .env is missing)
spotify_service = None
claude_service = None
extraction_service = None

def get_spotify_service():
    """Get or create Spotify service instance"""
    global spotify_service
    if spotify_service is None:
        spotify_service = SpotifyService()
    return spotify_service

def get_claude_service():
    """Get or create Claude service instance"""
    global claude_service
    if claude_service is None:
        claude_service = ClaudeService()
    return claude_service

def get_extraction_service():
    """Get or create Extraction service instance"""
    global extraction_service
    if extraction_service is None:
        extraction_service = ExtractionService()
    return extraction_service

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

@app.post("/chat")
async def chat(
    request: ChatRequest,
    playlist_id: str = Query(None, description="Optional playlist ID to automatically add extracted tracks"),
    authorization: str = Header(default=None, description="Optional Bearer token for adding tracks to playlist")
):
    """Send a chat message to Claude and get a streaming response"""
    async def generate():
        try:
            service = get_claude_service()
            
            # Convert Pydantic models to dict format
            messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
            
            # Log incoming request
            last_user_message = next((msg["content"] for msg in reversed(messages) if msg.get("role") == "user"), "N/A")
            logger.info(f"📨 Incoming chat request: {last_user_message[:100]}{'...' if len(last_user_message) > 100 else ''}")
            
            # Store extracted songs from the conversation
            extracted_songs = []
            failed_songs = []  # Track songs that failed Spotify validation
            already_extracted_songs = set()  # Track (track, artist) tuples to avoid duplicates
            
            # Get access token if playlist_id is provided
            access_token = None
            if playlist_id and authorization:
                if authorization.startswith("Bearer "):
                    access_token = authorization.replace("Bearer ", "")
                else:
                    access_token = authorization
            
            # Callback function to handle extracted songs (called one-by-one)
            def on_songs_extracted(songs: List[Dict[str, str]]):
                """Callback when songs are extracted from Claude's response (one song at a time)"""
                if not songs or len(songs) == 0:
                    return
                
                song = songs[0]  # Should only be one song at a time now
                extracted_songs.append(song)
                
                # Validate and add to playlist immediately if playlist_id and access_token are provided
                if playlist_id and access_token:
                    try:
                        spotify_service = get_spotify_service()
                        
                        track_uri = spotify_service.search_track(
                            access_token=access_token,
                            track_name=song.get("track", ""),
                            artist_name=song.get("artist")
                        )
                        
                        if track_uri:
                            # Add track immediately (one at a time)
                            spotify_service.add_tracks_to_playlist(
                                access_token=access_token,
                                playlist_id=playlist_id,
                                track_uris=[track_uri]
                            )
                            logger.info(f"✅ Added track to playlist: {song.get('track')} by {song.get('artist')}")
                        else:
                            # Track validation failed - add to failed list
                            failed_songs.append(song)
                            # Mark as already extracted so we don't try it again
                            track_key = (song.get("track", "").lower().strip(), song.get("artist", "").lower().strip())
                            already_extracted_songs.add(track_key)
                            logger.warning(f"❌ Track not found on Spotify: {song.get('track')} by {song.get('artist')}")
                    except Exception as e:
                        logger.error(f"❌ Failed to add track to playlist: {str(e)}")
                        failed_songs.append(song)
                        # Mark as already extracted so we don't try it again
                        track_key = (song.get("track", "").lower().strip(), song.get("artist", "").lower().strip())
                        already_extracted_songs.add(track_key)
                else:
                    logger.info(f"🎵 Song extracted (no playlist context): {song.get('track')} by {song.get('artist')}")
            
            # Stream response from Claude (with extraction callback)
            accumulated_response = ""
            for chunk in service.chat_stream(
                messages=messages, 
                system=request.system, 
                on_songs_extracted=on_songs_extracted,
                already_extracted_songs=already_extracted_songs
            ):
                accumulated_response += chunk
                # Send chunk as SSE event
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            # If there are failed songs, make a follow-up call to Claude to find alternatives
            if failed_songs and playlist_id and access_token:
                logger.info(f"⚠️ {len(failed_songs)} track(s) failed validation. Asking Claude to find alternatives.")
                
                # Build message asking Claude to find alternatives
                failed_tracks_text = "\n".join([f"- {song.get('track')} by {song.get('artist')}" for song in failed_songs])
                follow_up_message = f"""The following tracks could not be found on Spotify (they may not exist, have incorrect names, or incorrect artist information):

{failed_tracks_text}

IMPORTANT: You MUST first call set_mode with mode="build" before doing anything else. Then use search_web to find verified alternative tracks that match the same musical style/genre, and suggest them in the playlist format."""
                
                # Make follow-up call
                follow_up_messages = messages + [
                    {"role": "assistant", "content": accumulated_response},
                    {"role": "user", "content": follow_up_message}
                ]
                
                # Send separator before follow-up
                yield f"data: {json.dumps({'type': 'chunk', 'content': '\n\n'})}\n\n"
                
                for chunk in service.chat_stream(
                    messages=follow_up_messages,
                    system=request.system,
                    on_songs_extracted=on_songs_extracted,
                    already_extracted_songs=already_extracted_songs
                ):
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            # Send completion event
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
            logger.info(f"📤 Stream completed. Total songs extracted: {len(extracted_songs)}")
            if failed_songs:
                logger.info(f"❌ Songs that failed validation: {len(failed_songs)}")
                
        except ValueError as e:
            logger.error(f"❌ ValueError in chat endpoint: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        except Exception as e:
            logger.error(f"❌ Exception in chat endpoint: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'content': f'Failed to get response from Claude: {str(e)}'})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/playlists/{playlist_id}")
async def get_playlist(
    playlist_id: str,
    authorization: str = Header(..., description="Bearer token with access_token")
):
    """Get playlist details including tracks"""
    try:
        # Extract access token from Authorization header
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header. Expected 'Bearer <token>'")
        
        access_token = authorization.replace("Bearer ", "")
        
        # Get playlist
        spotify_service = get_spotify_service()
        playlist = spotify_service.get_playlist(
            access_token=access_token,
            playlist_id=playlist_id
        )
        
        return playlist
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get playlist: {str(e)}")

@app.post("/playlists/{playlist_id}/tracks")
async def add_tracks_to_playlist(
    playlist_id: str,
    request: AddTracksRequest,
    authorization: str = Header(..., description="Bearer token with access_token")
):
    """Add tracks to a playlist by their URIs"""
    try:
        # Extract access token from Authorization header
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header. Expected 'Bearer <token>'")
        
        access_token = authorization.replace("Bearer ", "")
        
        # Add tracks to playlist
        spotify_service = get_spotify_service()
        result = spotify_service.add_tracks_to_playlist(
            access_token=access_token,
            playlist_id=playlist_id,
            track_uris=request.track_uris
        )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to add tracks to playlist: {str(e)}")

@app.post("/tracks/search")
async def search_track(
    track: str = Query(..., description="Track name"),
    artist: str = Query(None, description="Artist name"),
    authorization: str = Header(..., description="Bearer token with access_token")
):
    """Search for a track on Spotify and return its URI"""
    try:
        # Extract access token from Authorization header
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header. Expected 'Bearer <token>'")
        
        access_token = authorization.replace("Bearer ", "")
        
        # Search for track
        spotify_service = get_spotify_service()
        track_uri = spotify_service.search_track(
            access_token=access_token,
            track_name=track,
            artist_name=artist
        )
        
        if track_uri:
            return {"uri": track_uri, "found": True}
        else:
            return {"uri": None, "found": False}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to search for track: {str(e)}")
    except ValueError as e:
        logger.error(f"❌ ValueError in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Exception in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get response from Claude: {str(e)}")

