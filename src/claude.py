"""
Claude API Client for MayaLite v0.4.

Enhanced with:
- Tool use support
- Vision support
- Usage tracking integration
"""

from typing import List, Dict, Any, Optional, Callable

import anthropic


class ClaudeClient:
    """
    Claude API client with tool use and vision support.
    
    Supports both:
    - API keys (sk-ant-api03-...) - pay-as-you-go
    - OAuth tokens (sk-ant-oat01-...) - Claude Max subscription
    """
    
    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int = 4096,
        usage_callback: Optional[Callable[[str, int, int], None]] = None,
    ):
        # Detect OAuth token vs API key
        if api_key.startswith("sk-ant-oat"):
            # OAuth token (Claude Max subscription)
            self.client = anthropic.Anthropic(auth_token=api_key)
        else:
            # API key (pay-as-you-go)
            self.client = anthropic.Anthropic(api_key=api_key)
        
        self.model = model
        self.max_tokens = max_tokens
        self._usage_callback = usage_callback
    
    def set_model(self, model: str) -> None:
        """Change the model being used."""
        self.model = model
    
    def set_usage_callback(self, callback: Callable[[str, int, int], None]) -> None:
        """Set callback for usage tracking (model, input_tokens, output_tokens)."""
        self._usage_callback = callback
    
    def _record_usage(self, response: Any) -> None:
        """Record usage if callback is set."""
        if self._usage_callback and hasattr(response, "usage"):
            self._usage_callback(
                self.model,
                response.usage.input_tokens,
                response.usage.output_tokens,
            )
    
    def chat(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Send a chat request to Claude.
        
        Args:
            system: System prompt (context)
            messages: List of {"role": "user"|"assistant", "content": str|list}
            max_tokens: Override default max_tokens
            tools: Optional list of tool definitions
        
        Returns:
            Assistant's response text
        """
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "system": system,
            "messages": messages,
        }
        
        if tools:
            kwargs["tools"] = tools
        
        response = self.client.messages.create(**kwargs)
        
        # Record usage
        self._record_usage(response)
        
        # Extract text from response
        if response.content and len(response.content) > 0:
            return response.content[0].text
        
        return ""
    
    def chat_with_tools(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        tool_handler: Callable[[str, Dict], Any],
        max_tokens: Optional[int] = None,
        max_iterations: int = 5,
    ) -> str:
        """
        Chat with automatic tool use handling.
        
        Args:
            system: System prompt
            messages: Conversation messages
            tools: Tool definitions
            tool_handler: Async function(tool_name, tool_input) -> result
            max_tokens: Override default
            max_iterations: Max tool use iterations
            
        Returns:
            Final assistant response text
        """
        current_messages = list(messages)
        
        for _ in range(max_iterations):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                system=system,
                messages=current_messages,
                tools=tools,
            )
            
            # Record usage
            self._record_usage(response)
            
            # Check if we need to handle tool use
            if response.stop_reason == "tool_use":
                # Build assistant message with all content blocks
                assistant_content = []
                tool_results = []
                
                for block in response.content:
                    if block.type == "text":
                        assistant_content.append({
                            "type": "text",
                            "text": block.text
                        })
                    elif block.type == "tool_use":
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                        
                        # Execute tool
                        try:
                            result = tool_handler(block.name, block.input)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": str(result),
                            })
                        except Exception as e:
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"Error: {str(e)}",
                                "is_error": True,
                            })
                
                # Add assistant message and tool results
                current_messages.append({
                    "role": "assistant",
                    "content": assistant_content,
                })
                current_messages.append({
                    "role": "user",
                    "content": tool_results,
                })
                
            else:
                # No more tool use, return final response
                for block in response.content:
                    if block.type == "text":
                        return block.text
                return ""
        
        # Max iterations reached
        return "I apologize, but I wasn't able to complete the request within the allowed iterations."
    
    def chat_with_vision(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Chat with vision support (images in messages).
        
        Messages can include image content blocks:
        {
            "role": "user",
            "content": [
                {"type": "image", "source": {...}},
                {"type": "text", "text": "..."}
            ]
        }
        
        Args:
            system: System prompt
            messages: Messages with potential image content
            max_tokens: Override default
            
        Returns:
            Assistant response text
        """
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=system,
            messages=messages,
        )
        
        # Record usage
        self._record_usage(response)
        
        if response.content and len(response.content) > 0:
            return response.content[0].text
        
        return ""
    
    def get_usage_info(self, response: Any) -> Dict[str, int]:
        """Extract token usage from a response."""
        if hasattr(response, "usage"):
            return {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        return {"input_tokens": 0, "output_tokens": 0}
