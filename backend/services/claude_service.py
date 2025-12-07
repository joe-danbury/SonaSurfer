import os
from anthropic import Anthropic
from typing import List, Dict, Optional
import yaml

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
    
    def chat(self, messages: List[Dict[str, str]], system: Optional[str] = None) -> str:
        """
        Send a chat message to Claude and get a response.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
                     Example: [{"role": "user", "content": "Hello!"}]
            system: Optional system message to set Claude's behavior
        
        Returns:
            Claude's response text
        """
        try:
            # Prepare the message list for Anthropic API
            # Anthropic expects messages in a specific format
            api_messages = []
            for msg in messages:
                if msg.get('role') == 'user' or msg.get('role') == 'assistant':
                    api_messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
            
            # Make the API call
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=api_messages,
                system=system
            )
            
            # Extract text from response
            # Anthropic returns content as a list of content blocks
            if response.content and len(response.content) > 0:
                return response.content[0].text
            else:
                return ""
                
        except Exception as e:
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
            
            with self.client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=api_messages,
                system=system
            ) as stream:
                for text_block in stream.text_stream:
                    yield text_block
                    
        except Exception as e:
            raise Exception(f"Failed to stream response from Claude: {str(e)}")
