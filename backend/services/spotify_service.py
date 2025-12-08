import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from typing import Optional, Dict, List
import yaml
import logging

logger = logging.getLogger(__name__)

class SpotifyService:
    def __init__(self):
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
        
        # Validate environment variables
        if not self.client_id:
            raise ValueError("SPOTIFY_CLIENT_ID environment variable is not set. Check your .env file.")
        if not self.client_secret:
            raise ValueError("SPOTIFY_CLIENT_SECRET environment variable is not set. Check your .env file.")
        if not self.redirect_uri:
            raise ValueError("SPOTIFY_REDIRECT_URI environment variable is not set. Check your .env file.")
        
        # Load scopes from config
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        with open(config_path) as f:
            config = yaml.safe_load(f)
        self.scopes = " ".join(config['spotify']['scopes'])
        
        # Initialize SpotifyOAuth helper
        self.oauth = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scopes,
            show_dialog=True
        )
    
    def get_auth_url(self, state: Optional[str] = None) -> str:
        """Generate Spotify authorization URL"""
        auth_url = self.oauth.get_authorize_url(state=state)
        return auth_url
    
    def exchange_code_for_token(self, code: str) -> Dict:
        """Exchange authorization code for access/refresh tokens"""
        try:
            # Use spotipy's method to exchange code
            token_info = self.oauth.get_access_token(code, as_dict=True)
            return token_info
        except Exception as e:
            raise Exception(f"Failed to exchange code for token: {str(e)}")
    
    def get_spotify_client(self, access_token: str):
        """Create Spotipy client with user's access token"""
        return spotipy.Spotify(auth=access_token)
    
    def refresh_access_token(self, refresh_token: str) -> Dict:
        """Refresh expired access token using refresh token"""
        try:
            # Create a new OAuth instance for refresh
            oauth = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=self.scopes
            )
            token_info = oauth.refresh_access_token(refresh_token)
            return token_info
        except Exception as e:
            raise Exception(f"Failed to refresh token: {str(e)}")
    
    def create_playlist(self, access_token: str, name: str, description: Optional[str] = None, public: bool = True) -> Dict:
        """Create a new playlist for the authenticated user"""
        try:
            spotify = self.get_spotify_client(access_token)
            
            # Get current user's ID
            user = spotify.current_user()
            user_id = user['id']
            
            # Create playlist
            playlist = spotify.user_playlist_create(
                user=user_id,
                name=name,
                public=public,
                description=description
            )
            
            return playlist
        except Exception as e:
            raise Exception(f"Failed to create playlist: {str(e)}")
    
    def search_track(self, access_token: str, track_name: str, artist_name: Optional[str] = None) -> Optional[str]:
        """
        Search for a track on Spotify and return its URI.
        
        Args:
            access_token: User's Spotify access token
            track_name: Name of the track
            artist_name: Optional artist name to improve search accuracy
        
        Returns:
            Track URI (spotify:track:xxx) if found, None otherwise
        """
        try:
            spotify = self.get_spotify_client(access_token)
            
            # Build search query
            if artist_name:
                query = f"track:{track_name} artist:{artist_name}"
            else:
                query = track_name
            
            logger.info(f"🔍 Searching Spotify for: {query}")
            
            # Search for track
            results = spotify.search(q=query, type='track', limit=1)
            
            if results['tracks']['items']:
                track = results['tracks']['items'][0]
                track_uri = track['uri']
                logger.info(f"✅ Found track: {track['name']} by {track['artists'][0]['name']} - URI: {track_uri}")
                return track_uri
            else:
                logger.warning(f"⚠️ No track found for: {query}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error searching for track '{track_name}': {str(e)}")
            return None
    
    def get_playlist(self, access_token: str, playlist_id: str) -> Dict:
        """
        Get playlist details including tracks.
        
        Args:
            access_token: User's Spotify access token
            playlist_id: Spotify playlist ID
        
        Returns:
            Playlist dictionary with tracks
        """
        try:
            spotify = self.get_spotify_client(access_token)
            playlist = spotify.playlist(playlist_id)
            return playlist
        except Exception as e:
            raise Exception(f"Failed to get playlist: {str(e)}")
    
    def add_tracks_to_playlist(self, access_token: str, playlist_id: str, track_uris: List[str]) -> Dict:
        """
        Add tracks to a playlist.
        
        Args:
            access_token: User's Spotify access token
            playlist_id: Spotify playlist ID
            track_uris: List of track URIs (spotify:track:xxx)
        
        Returns:
            Dictionary with snapshot_id from Spotify
        """
        try:
            spotify = self.get_spotify_client(access_token)
            
            # Filter out None values (tracks that weren't found)
            valid_uris = [uri for uri in track_uris if uri is not None]
            
            if not valid_uris:
                logger.warning("⚠️ No valid track URIs to add")
                return {"snapshot_id": None, "added": 0}
            
            logger.info(f"➕ Adding {len(valid_uris)} track(s) to playlist {playlist_id}")
            
            # Add tracks to playlist (Spotify allows up to 100 at a time)
            # Split into batches of 100 if needed
            added_count = 0
            for i in range(0, len(valid_uris), 100):
                batch = valid_uris[i:i+100]
                result = spotify.playlist_add_items(playlist_id=playlist_id, items=batch)
                added_count += len(batch)
                logger.info(f"✅ Added batch of {len(batch)} tracks. Snapshot ID: {result.get('snapshot_id')}")
            
            return {"snapshot_id": result.get('snapshot_id'), "added": added_count}
            
        except Exception as e:
            logger.error(f"❌ Error adding tracks to playlist: {str(e)}")
            raise Exception(f"Failed to add tracks to playlist: {str(e)}")
