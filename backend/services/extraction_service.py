import os
import json
import re
import logging
from anthropic import Anthropic
from typing import List, Dict, Optional, Set, Tuple

# Set up logging
logger = logging.getLogger(__name__)

class ExtractionService:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        
        # Validate API key
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set. Check your .env file.")
        
        # Initialize Anthropic client
        self.client = Anthropic(api_key=self.api_key)
        
        # Use Haiku model for faster, cheaper extraction
        self.model = "claude-3-5-haiku-20241022"
        
        # System prompt for JSON extraction
        self.system_prompt = "You are a JSON extraction assistant. Extract song recommendations and return ONLY valid JSON array, nothing else."
    
    def _extract_single_song_with_regex(self, text: str) -> Optional[Dict[str, str]]:
        """
        Try to extract a single song using regex patterns.
        Looks for patterns like: "Track Title" — Artist or Track Title — Artist
        
        Returns:
            Dict with 'track' and 'artist' keys if found, None otherwise
        """
        # Pattern 1: "Track Title" — Artist (with em dash or double dash)
        pattern1 = r'["\']([^"\']+)["\']\s*[—–-]\s*([^\n,]+)'
        match1 = re.search(pattern1, text)
        if match1:
            track = match1.group(1).strip()
            artist = match1.group(2).strip().rstrip('.,;:')
            if track and artist:
                return {"track": track, "artist": artist}
        
        # Pattern 2: Numbered list: "1. Track Title" — Artist
        pattern2 = r'\d+\.\s*["\']?([^"\']+)["\']?\s*[—–-]\s*([^\n,]+)'
        match2 = re.search(pattern2, text)
        if match2:
            track = match2.group(1).strip()
            artist = match2.group(2).strip().rstrip('.,;:')
            if track and artist:
                return {"track": track, "artist": artist}
        
        # Pattern 3: "Track Title" by Artist
        pattern3 = r'["\']([^"\']+)["\']\s+by\s+([^\n,]+)'
        match3 = re.search(pattern3, text, re.IGNORECASE)
        if match3:
            track = match3.group(1).strip()
            artist = match3.group(2).strip().rstrip('.,;:')
            if track and artist:
                return {"track": track, "artist": artist}
        
        return None
    
    def extract_new_songs_incremental(self, text: str, already_extracted: Set[Tuple[str, str]]) -> List[Dict[str, str]]:
        """
        Extract songs one-by-one from text, only returning new songs not already extracted.
        
        Args:
            text: Text to extract songs from
            already_extracted: Set of (track, artist) tuples already extracted
        
        Returns:
            List of new song dictionaries
        """
        new_songs = []
        
        # Try regex extraction first (faster)
        song = self._extract_single_song_with_regex(text)
        if song:
            track_key = (song["track"].lower().strip(), song["artist"].lower().strip())
            if track_key not in already_extracted:
                new_songs.append(song)
                return new_songs
        
        # Fallback: Use Claude extraction for the entire text, but filter out already extracted
        all_songs = self.extract_songs(text)
        for song in all_songs:
            track_key = (song["track"].lower().strip(), song["artist"].lower().strip())
            if track_key not in already_extracted:
                new_songs.append(song)
        
        return new_songs
    
    def extract_songs(self, response_text: str) -> List[Dict[str, str]]:
        """
        Extract song recommendations from Claude's conversational response.
        
        Args:
            response_text: The conversational text from Claude containing song recommendations
        
        Returns:
            List of dictionaries with 'track' and 'artist' keys
            Example: [{"track": "Song Name", "artist": "Artist Name"}, ...]
        """
        try:
            # Build user prompt
            user_prompt = f"""Extract all song recommendations from the following text.

For each song mentioned, identify:
- Track name
- Artist name

Return ONLY a JSON array with no other text or markdown:
[
    {{"track": "Song Name", "artist": "Artist Name"}},
    ...
]

If no songs are found, return an empty array: []

Text to parse:
{response_text}"""
            
            logger.info("🎯 Starting song extraction from Claude response")
            
            # Make API call to Claude for extraction
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                system=self.system_prompt
            )
            
            # Extract text from response
            extracted_text = ""
            if response.content and len(response.content) > 0:
                extracted_text = response.content[0].text.strip()
            
            # Strip markdown code fences if present (```json ... ``` or ``` ... ```)
            extracted_text = re.sub(r'^```(?:json)?\s*\n', '', extracted_text, flags=re.MULTILINE)
            extracted_text = re.sub(r'\n```\s*$', '', extracted_text, flags=re.MULTILINE)
            extracted_text = extracted_text.strip()
            
            # Parse JSON
            try:
                songs = json.loads(extracted_text)
                
                # Validate structure
                if not isinstance(songs, list):
                    logger.warning(f"⚠️ Extracted data is not a list: {type(songs)}")
                    return []
                
                # Validate each item has required keys
                valid_songs = []
                for song in songs:
                    if isinstance(song, dict) and "track" in song and "artist" in song:
                        valid_songs.append({
                            "track": str(song["track"]).strip(),
                            "artist": str(song["artist"]).strip()
                        })
                    else:
                        logger.warning(f"⚠️ Invalid song format: {song}")
                
                # Log the full list of extracted songs
                logger.info(f"📝 Extracted text from Claude: {json.dumps(valid_songs, indent=2)}")
                logger.info(f"✅ Successfully extracted {len(valid_songs)} song(s)")
                return valid_songs
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON parsing error: {str(e)}")
                logger.error(f"Failed to parse: {extracted_text}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error in song extraction: {str(e)}")
            return []

