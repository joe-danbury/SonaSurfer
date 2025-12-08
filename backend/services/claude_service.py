import os
from anthropic import Anthropic
from typing import List, Dict, Optional
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
            }
        ]
    
    def search_web(self, query: str) -> str:
        """
        Search the web using DuckDuckGo and return results.
        
        Args:
            query: Search query string
        
        Returns:
            Formatted search results as a string
        """
        logger.info(f"🔍 Web search requested: {query}")
        try:
            # Use DuckDuckGo HTML search (no API key required)
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            with httpx.Client(timeout=10.0, headers=headers) as client:
                response = client.get(search_url)
                response.raise_for_status()
                
                html = response.text
                results = []
                import re
                
                # Try multiple patterns to find DuckDuckGo results
                # Pattern 1: Modern DuckDuckGo HTML structure
                pattern1 = r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]*)"[^>]*>([^<]+)</a>'
                matches1 = re.findall(pattern1, html, re.IGNORECASE)
                
                # Pattern 2: Alternative structure with data-testid or other attributes
                pattern2 = r'<a[^>]*href="([^"]*)"[^>]*class="[^"]*result[^"]*"[^>]*>.*?<span[^>]*>([^<]+)</span>'
                matches2 = re.findall(pattern2, html, re.IGNORECASE | re.DOTALL)
                
                # Pattern 3: Look for links in result containers
                pattern3 = r'<div[^>]*class="[^"]*result[^"]*"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>'
                matches3 = re.findall(pattern3, html, re.IGNORECASE | re.DOTALL)
                
                # Combine all matches
                all_matches = matches1 + matches2 + matches3
                
                # Extract unique results
                seen_urls = set()
                for url, title in all_matches:
                    # Clean up URL (DuckDuckGo sometimes has encoded URLs)
                    if url.startswith('//'):
                        url = 'https:' + url
                    elif url.startswith('/l/?kh='):
                        # DuckDuckGo redirect URL, try to extract actual URL
                        url_match = re.search(r'uddg=([^&]+)', url)
                        if url_match:
                            from urllib.parse import unquote
                            url = unquote(url_match.group(1))
                    
                    # Clean up title
                    title = re.sub(r'<[^>]+>', '', title).strip()
                    title = re.sub(r'\s+', ' ', title)  # Normalize whitespace
                    
                    # Skip if we've seen this URL or if it's invalid
                    if url and title and url not in seen_urls and url.startswith('http'):
                        seen_urls.add(url)
                        results.append(f"Title: {title}\nURL: {url}")
                        if len(results) >= 5:  # Limit to top 5
                            break
                
                if results:
                    logger.info(f"✅ Web search completed. Found {len(results)} results for: {query}")
                    return "\n\n".join(results)
                else:
                    # Log the HTML structure for debugging (first 500 chars)
                    logger.warning(f"⚠️ Web search completed but no results parsed for: {query}")
                    logger.debug(f"HTML preview (first 500 chars): {html[:500]}")
                    return f"Search performed for: {query}\n(Results parsing may need improvement)"
                    
        except Exception as e:
            logger.error(f"❌ Web search error for query '{query}': {str(e)}")
            return f"Error performing web search: {str(e)}"
    
    def chat(self, messages: List[Dict[str, str]], system: Optional[str] = None) -> str:
        """
        Send a chat message to Claude and get a response.
        Handles tool calls automatically.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
                     Example: [{"role": "user", "content": "Hello!"}]
            system: Optional system message to set Claude's behavior
        
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
            
            # Make the API call with tools
            api_params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": api_messages,
                "tools": self.tools
            }
            if system:
                api_params["system"] = system
            
            # Loop to handle tool calls
            max_iterations = 15  # Prevent infinite loops
            iteration = 0
            accumulated_text = ""  # Accumulate all text responses across iterations
            
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
                
                # Accumulate text from this iteration
                if text_content:
                    accumulated_text += text_content
                    logger.info(f"💬 Claude response: {text_content[:200]}{'...' if len(text_content) > 200 else ''}")
                
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
