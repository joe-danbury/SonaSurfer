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
    
    def extract_new_songs_incremental(self, text: str, already_extracted: Set[Tuple[str, str]]) -> List[Dict[str, str]]:
        """
        Extract songs from text using Claude extraction, only returning new songs not already extracted.
        
        Args:
            text: Text to extract songs from
            already_extracted: Set of (track, artist) tuples already extracted
        
        Returns:
            List of new song dictionaries
        """
        # Use Claude extraction to get all songs from text
        all_songs = self.extract_songs(text)
        
        # Filter out songs that were already extracted
        new_songs = []
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

