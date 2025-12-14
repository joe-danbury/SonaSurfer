import os
from anthropic import Anthropic
from typing import List, Dict, Optional, Callable, Set, Tuple
import yaml
import httpx
import json
import logging
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

# Set up logging
logger = logging.getLogger(__name__)

class ClaudeService:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        
        # Validate API key
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set. Check your .env file.")
        
        # Initialize Anthropic client
        self.client = Anthropic(api_key=self.api_key)
        
        # Load config
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        self.model = config['claude']['model']
        self.max_tokens = config['claude']['max_tokens']
        
        # Define available tools
        self.tools = [
            {
                "name": "search_web",
                "description": "Search the web for current information. CRITICAL: When searching for songs by a specific artist, you MUST search for the artist's Wikipedia discography page (e.g., 'Artist Name discography Wikipedia'). Only suggest tracks that appear on the artist's official Wikipedia discography page. Use this tool to verify track names, artist names, and that tracks actually exist.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query. For artist songs, use format: 'Artist Name discography Wikipedia' to find their official discography page."
                        }
                    },
                    "required": ["query"]
                }
            }
        ]
    
    def search_web(self, query: str) -> str:
        """
        Search the web using Brave Search API, fetch page content, and return results with actual content.
        
        Args:
            query: Search query string
        
        Returns:
            Formatted search results with page content as a string
        """
        logger.info(f"🔍 Web search requested: {query}")
        try:
            api_key = os.getenv("BRAVE_API_KEY")
            if not api_key:
                raise ValueError("BRAVE_API_KEY environment variable is not set. Check your .env file.")
            
            # Use Brave Search API
            search_url = "https://api.search.brave.com/res/v1/web/search"
            
            headers = {
                "X-Subscription-Token": api_key,
                "Accept": "application/json"
            }
            
            params = {
                "q": query,
                "count": 5
            }
            
            with httpx.Client(timeout=10.0, headers=headers) as client:
                response = client.get(search_url, params=params)
                response.raise_for_status()
                
                data = response.json()
                results = []
                
                # Extract results from Brave API response
                web_results = data.get("web", {}).get("results", [])
                
                for result in web_results:
                    title = result.get("title", "").strip()
                    url = result.get("url", "").strip()
                    
                    if url and title:
                        # Fetch the actual page content
                        page_content = self._fetch_page_content(url)
                        if page_content:
                            results.append(f"Title: {title}\nURL: {url}\nContent:\n{page_content}")
                        else:
                            # Fallback to just title and URL if content fetch fails
                            results.append(f"Title: {title}\nURL: {url}\n(Content unavailable)")
                
                if results:
                    logger.info(f"✅ Web search completed. Found {len(results)} results with content for: {query}")
                    return "\n\n---\n\n".join(results)
                else:
                    logger.warning(f"⚠️ Web search completed but no results parsed for: {query}")
                    return f"Search performed for: {query}\n(Results parsing may need improvement)"
                    
        except Exception as e:
            logger.error(f"❌ Web search error for query '{query}': {str(e)}")
            return f"Error performing web search: {str(e)}"
    
    def _fetch_page_content(self, url: str, max_length: int = 10000) -> Optional[str]:
        """
        Fetch and extract text content from a web page.
        
        Args:
            url: URL of the page to fetch
            max_length: Maximum length of content to return (to avoid token limits)
        
        Returns:
            Extracted text content from the page, or None if fetch fails
        """
        try:
            # Set a reasonable timeout and user agent
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            with httpx.Client(timeout=15.0, headers=headers, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                
                # Parse HTML and extract text
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                
                # Get text content
                text = soup.get_text(separator='\n', strip=True)
                
                # Clean up excessive whitespace
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                text = '\n'.join(lines)
                
                # Limit length to avoid token limits
                if len(text) > max_length:
                    text = text[:max_length] + "... (content truncated)"
                
                logger.info(f"📄 Fetched {len(text)} chars from {url}")
                return text
                
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch content from {url}: {str(e)}")
            return None
    
    def chat_stream(self, messages: List[Dict[str, str]], system: Optional[str] = None, on_songs_extracted: Optional[Callable[[List[Dict[str, str]]], None]] = None, already_extracted_songs: Optional[Set[Tuple[str, str]]] = None, successfully_added_songs: Optional[List[Dict[str, str]]] = None):
        """
        Stream a chat message to Claude and get responses incrementally.
        Handles tool calls automatically.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
                     Example: [{"role": "user", "content": "Hello!"}]
            system: Optional system message to set Claude's behavior
            on_songs_extracted: Optional callback for when songs are extracted (only called in 'build' mode)
            successfully_added_songs: List of songs that were successfully added to playlist (for feedback)
        
        Yields:
            Text chunks as they arrive from Claude
        """
        try:
            # Prepare the message list for Anthropic API
            api_messages = []
            for msg in messages:
                role = msg.get('role')
                if role == 'user' or role == 'assistant':
                    # Handle both string content and tool use content
                    content = msg.get('content', '')
                    if isinstance(content, str):
                        api_messages.append({
                            "role": role,
                            "content": content
                        })
                    else:
                        # If content is already in API format (with tool_use blocks)
                        api_messages.append({
                            "role": role,
                            "content": content
                        })
                elif role == 'tool':
                    # Tool result message
                    api_messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": msg.get('tool_use_id'),
                            "content": msg.get('content', '')
                        }]
                    })
            
            # Build system prompt - always in build mode
            default_system = """You are a helpful music assistant for SonaSurfer, a playlist creation app. You are always in BUILD MODE, which means you should help users create and build playlists by suggesting songs.

BUILD MODE RULES (STRICTLY ENFORCED):

WIKIPEDIA DISCOGRAPHY REQUIREMENT (MANDATORY):
- When the user mentions a specific artist or you need to suggest songs by an artist, you MUST:
  1. Search for the artist's Wikipedia discography page using: "Artist Name discography Wikipedia"
  2. ONLY suggest tracks that are listed on the artist's official Wikipedia discography page
  3. Do NOT suggest tracks from other sources or based on your training data
  4. The Wikipedia discography page is the ONLY source of truth for an artist's songs

WEB SEARCH REQUIREMENT (MANDATORY):
- You CANNOT suggest tracks without first using the search_web tool. This is IMPOSSIBLE.
- NEVER suggest tracks based on your training data alone - it may be outdated, incorrect, or incomplete.
- BEFORE suggesting ANY tracks, you MUST use search_web to verify track names, artist names, and that tracks actually exist.
- For artist-specific requests, ALWAYS search for the artist's Wikipedia discography page first
- If web search fails to find relevant information or returns no useful results, DO NOT make up tracks.
- Instead, tell the user: "I couldn't find verified tracks matching your request. Could you provide more specific details or try a different search?"
- It is BETTER to tell the user you couldn't find tracks than to hallucinate fake track names.

OUTPUT FORMAT RULES:
- Only suggest individual tracks (songs).
- Do not suggest albums, EPs, suites, playlists, projects, or "arrangements".
- If you want to recommend an album, pick 1–3 specific tracks from it instead.
- Each recommendation must be in the exact format:
  "Track Title" — Artist
  (No extra punctuation inside the title unless it's part of the official name.)

WORKFLOW:
1. If user mentions a specific artist, search for: "Artist Name discography Wikipedia"
2. Review the Wikipedia discography page to find appropriate tracks
3. Only suggest tracks that appear on the official Wikipedia discography page
4. Use search_web to verify any other tracks that match the user's request
5. Only after web search confirms real tracks exist, suggest them in the required format
6. If web search fails or finds nothing, inform the user honestly - do NOT invent tracks
7. IMPORTANT: Once you have suggested tracks in your response, do NOT mention them again or try to verify them again. Move on to suggesting new tracks or conclude your response. Do not repeat the same track suggestions."""
            
            # Make the API call with tools
            api_params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": api_messages,
                "tools": self.tools,
                "system": default_system if not system else f"{default_system}\n\n{system}"
            }
            
            # Loop to handle tool calls
            max_iterations = 15  # Prevent infinite loops
            iteration = 0
            accumulated_text = ""  # Accumulate all text responses across iterations
            current_mode = "build"  # Always in build mode
            
            # Track already extracted songs to avoid duplicates (using (track, artist) tuples as keys)
            if already_extracted_songs is None:
                already_extracted_songs = set()
            
            # Track successfully added songs for stopping early
            if successfully_added_songs is None:
                successfully_added_songs = []
            
            while iteration < max_iterations:
                logger.info(f"📤 Sending request to Claude (iteration {iteration + 1})")
                response = self.client.messages.create(**api_params)
                
                # Check if Claude wants to use a tool
                tool_uses = []
                text_content = ""
                
                for block in response.content:
                    if block.type == "text":
                        text_content += block.text
                    elif block.type == "tool_use":
                        tool_uses.append(block)
                
                # Yield text from this iteration immediately
                if text_content:
                    # Signal new bubble for subsequent iterations (after tool processing)
                    if iteration > 0:
                        yield {"type": "new_bubble"}
                        logger.info("📝 Starting new message bubble")
                    
                    accumulated_text += text_content
                    logger.info(f"💬 Claude response: {text_content[:200]}{'...' if len(text_content) > 200 else ''}")
                    # Yield the text chunk immediately
                    yield {"type": "text", "content": text_content}
                    
                    # Extract songs incrementally from accumulated text (always in build mode)
                    if on_songs_extracted:
                        try:
                            from services.extraction_service import ExtractionService
                            extraction_service = ExtractionService()
                            
                            # Extract new songs from accumulated text (one-by-one style)
                            new_songs = extraction_service.extract_new_songs_incremental(accumulated_text, already_extracted_songs)
                            
                            if new_songs:
                                # Add newly extracted songs to the tracking set
                                for song in new_songs:
                                    track_key = (song["track"].lower().strip(), song["artist"].lower().strip())
                                    already_extracted_songs.add(track_key)
                                
                                logger.info(f"🎵 Extracted {len(new_songs)} new song(s) from Claude response")
                                
                                # Call callback with all new songs (callback will create async tasks)
                                on_songs_extracted(new_songs)
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to extract songs: {str(e)}")
                
                # If no tool uses, we're done
                if not tool_uses:
                    logger.info("✅ Claude response complete (no tool calls)")
                    if successfully_added_songs and len(successfully_added_songs) > 0:
                        logger.info(f"🎵 Playlist complete - {len(successfully_added_songs)} track(s) successfully added")
                    return
                
                # If we have enough songs (10+), stop the tool call loop
                if successfully_added_songs and len(successfully_added_songs) >= 10:
                    logger.info(f"🛑 Stopping tool loop - {len(successfully_added_songs)} track(s) already added to playlist.")
                    yield {"type": "new_bubble"}
                    yield {"type": "text", "content": f"\n\nYour playlist now has {len(successfully_added_songs)} tracks! Let me know if you'd like me to add more."}
                    return
                
                # Log tool calls
                logger.info(f"🔧 Claude requested {len(tool_uses)} tool call(s):")
                for tool_use in tool_uses:
                    logger.info(f"   - Tool: {tool_use.name} (ID: {tool_use.id})")
                    if tool_use.name == "search_web":
                        query = tool_use.input.get("query", "")
                        logger.info(f"     Query: {query}")
                
                # Execute tools and add results to conversation
                tool_results = []
                for tool_use in tool_uses:
                    if tool_use.name == "search_web":
                        query = tool_use.input.get("query", "")
                        result = self.search_web(query)
                        logger.info(f"📥 Tool result received (length: {len(result)} chars)")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": result
                        })
                    else:
                        # Unknown tool - log warning
                        logger.warning(f"⚠️ Unknown tool requested: {tool_use.name}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": f"Unknown tool: {tool_use.name}"
                        })
                
                # Add assistant's message with tool use to conversation
                api_messages.append({
                    "role": "assistant",
                    "content": response.content
                })
                
                # Add tool results to conversation
                api_messages.append({
                    "role": "user",
                    "content": tool_results
                })
                
                # Inject context about songs already added to the playlist
                # This helps Claude know what NOT to suggest again
                if successfully_added_songs and len(successfully_added_songs) > 0:
                    added_songs_list = "\n".join([
                        f"- \"{song['track']}\" by {song['artist']}" 
                        for song in successfully_added_songs
                    ])
                    context_message = f"""IMPORTANT CONTEXT: The following {len(successfully_added_songs)} track(s) have ALREADY been added to the playlist. Do NOT suggest these again:

{added_songs_list}

Please suggest DIFFERENT tracks that are not in the list above."""
                    
                    # Add as a follow-up user message
                    api_messages.append({
                        "role": "user", 
                        "content": context_message
                    })
                    logger.info(f"📝 Injected context: {len(successfully_added_songs)} track(s) already in playlist")
                
                iteration += 1
                logger.info(f"🔄 Continuing conversation with tool results (iteration {iteration})")
            
            # If we've done max iterations, we're done
            logger.warning(f"⚠️ Maximum tool call iterations ({max_iterations}) reached")
            if accumulated_text:
                yield {"type": "text", "content": "Maximum tool call iterations reached."}
                
        except Exception as e:
            logger.error(f"❌ Error in Claude chat: {str(e)}")
            yield {"type": "error", "content": str(e)}
    
    def chat(self, messages: List[Dict[str, str]], system: Optional[str] = None, on_songs_extracted: Optional[Callable[[List[Dict[str, str]]], None]] = None, already_extracted_songs: Optional[Set[Tuple[str, str]]] = None, successfully_added_songs: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Send a chat message to Claude and get a response (non-streaming version).
        Handles tool calls automatically.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
                     Example: [{"role": "user", "content": "Hello!"}]
            system: Optional system message to set Claude's behavior
            on_songs_extracted: Optional callback for when songs are extracted (only called in 'build' mode)
            successfully_added_songs: List of songs that were successfully added to playlist (for feedback)
        
        Returns:
            Claude's response text (accumulated from all chunks)
        """
        # Use the streaming version and accumulate results
        accumulated = ""
        for chunk in self.chat_stream(messages, system, on_songs_extracted, already_extracted_songs, successfully_added_songs):
            if isinstance(chunk, dict) and chunk.get("type") == "text":
                accumulated += chunk.get("content", "")
            elif isinstance(chunk, str):
                accumulated += chunk
        return accumulated
    
    def stream_chat(self, messages: List[Dict[str, str]], system: Optional[str] = None):
        """
        Stream a chat response from Claude.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            system: Optional system message
        
        Yields:
            Text chunks as they arrive
        """
        try:
            api_messages = []
            for msg in messages:
                if msg.get('role') == 'user' or msg.get('role') == 'assistant':
                    api_messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
            
            # Only include system parameter if it's provided
            api_params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": api_messages
            }
            if system:
                api_params["system"] = system
            
            with self.client.messages.stream(**api_params) as stream:
                for text_block in stream.text_stream:
                    yield text_block
                    
        except Exception as e:
            raise Exception(f"Failed to stream response from Claude: {str(e)}")
