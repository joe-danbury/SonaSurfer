import os
from anthropic import Anthropic
from typing import List, Dict, Optional, Callable
import yaml
import httpx
import json
import logging
from urllib.parse import quote_plus

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
                "description": "Search the web for current information, news, facts, or any topic. Use this when you need up-to-date information that you don't have in your training data.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to look up on the web"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "set_mode",
                "description": "Set the conversation mode based on user intent. Use 'build' when the user wants to create, build, or add songs to a playlist. Use 'chat' for general conversation, questions about music/artists, or discussions that don't involve playlist creation.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["build", "chat"],
                            "description": "The conversation mode: 'build' for playlist building/adding songs, 'chat' for general conversation"
                        }
                    },
                    "required": ["mode"]
                }
            }
        ]
    
    def search_web(self, query: str) -> str:
        """
        Search the web using Brave Search API and return results.
        
        Args:
            query: Search query string
        
        Returns:
            Formatted search results as a string
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
                        results.append(f"Title: {title}\nURL: {url}")
                
                if results:
                    logger.info(f"✅ Web search completed. Found {len(results)} results for: {query}")
                    return "\n\n".join(results)
                else:
                    logger.warning(f"⚠️ Web search completed but no results parsed for: {query}")
                    return f"Search performed for: {query}\n(Results parsing may need improvement)"
                    
        except Exception as e:
            logger.error(f"❌ Web search error for query '{query}': {str(e)}")
            return f"Error performing web search: {str(e)}"
    
    def chat(self, messages: List[Dict[str, str]], system: Optional[str] = None, on_songs_extracted: Optional[Callable[[List[Dict[str, str]]], None]] = None) -> str:
        """
        Send a chat message to Claude and get a response.
        Handles tool calls automatically.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
                     Example: [{"role": "user", "content": "Hello!"}]
            system: Optional system message to set Claude's behavior
            on_songs_extracted: Optional callback for when songs are extracted (only called in 'build' mode)
        
        Returns:
            Claude's response text
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
            
            # Build system prompt - guide Claude to use set_mode tool
            default_system = """You are a helpful music assistant for SonaSurfer, a playlist creation app.

IMPORTANT: At the start of each conversation turn, determine the user's intent:
- If they want to CREATE, BUILD, or ADD SONGS to a playlist → call set_mode with mode="build"
- If they're just chatting, asking questions, or discussing music → call set_mode with mode="chat"

Only extract and recommend songs when in "build" mode. In "chat" mode, just have a conversation."""
            
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
            current_mode = "chat"  # Default mode, Claude will set this via set_mode tool
            
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
                
                # Process set_mode tool calls FIRST to update mode before extraction check
                set_mode_calls = [tu for tu in tool_uses if tu.name == "set_mode"]
                for tool_use in set_mode_calls:
                    mode = tool_use.input.get("mode", "chat")
                    current_mode = mode  # Update mode state immediately
                    logger.info(f"🎯 Mode set to: {mode}")
                
                # Accumulate text from this iteration
                if text_content:
                    accumulated_text += text_content
                    logger.info(f"💬 Claude response: {text_content[:200]}{'...' if len(text_content) > 200 else ''}")
                    
                    # Extract songs from this response ONLY if in 'build' mode
                    if on_songs_extracted and current_mode == "build":
                        try:
                            from services.extraction_service import ExtractionService
                            extraction_service = ExtractionService()
                            songs = extraction_service.extract_songs(text_content)
                            if songs:
                                logger.info(f"🎵 Extracted {len(songs)} song(s) from Claude response (build mode)")
                                on_songs_extracted(songs)
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to extract songs: {str(e)}")
                    elif current_mode == "chat":
                        logger.info("💬 Chat mode - skipping song extraction")
                
                # If no tool uses, return the accumulated text response
                if not tool_uses:
                    logger.info("✅ Claude response complete (no tool calls)")
                    return accumulated_text if accumulated_text else ""
                
                # Log tool calls
                logger.info(f"🔧 Claude requested {len(tool_uses)} tool call(s):")
                for tool_use in tool_uses:
                    logger.info(f"   - Tool: {tool_use.name} (ID: {tool_use.id})")
                    if tool_use.name == "search_web":
                        query = tool_use.input.get("query", "")
                        logger.info(f"     Query: {query}")
                    elif tool_use.name == "set_mode":
                        mode = tool_use.input.get("mode", "")
                        logger.info(f"     Mode: {mode}")
                
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
                    elif tool_use.name == "set_mode":
                        mode = tool_use.input.get("mode", "chat")
                        # Mode already updated above, just return confirmation
                        logger.info(f"🎯 Confirming mode: {mode}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": f"Mode set to {mode}"
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
                
                iteration += 1
                logger.info(f"🔄 Continuing conversation with tool results (iteration {iteration})")
            
            # If we've done max iterations, return the accumulated text content
            logger.warning(f"⚠️ Maximum tool call iterations ({max_iterations}) reached")
            return accumulated_text if accumulated_text else "Maximum tool call iterations reached."
                
        except Exception as e:
            logger.error(f"❌ Error in Claude chat: {str(e)}")
            raise Exception(f"Failed to get response from Claude: {str(e)}")
    
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
