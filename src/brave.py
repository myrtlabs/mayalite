"""
Brave Search API client for MayaLite v0.4.

Provides web search functionality via Brave Search API.
"""

import aiohttp
import requests
from typing import Optional, List, Dict, Any


class BraveSearchClient:
    """Client for Brave Search API."""
    
    BASE_URL = "https://api.search.brave.com/res/v1/web/search"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._enabled = bool(api_key)
    
    @property
    def enabled(self) -> bool:
        """Check if search is enabled (API key configured)."""
        return self._enabled
    
    async def search(
        self,
        query: str,
        count: int = 5,
        country: str = "US",
        search_lang: str = "en"
    ) -> dict:
        """
        Search the web using Brave Search API.
        
        Args:
            query: Search query string
            count: Number of results (1-20)
            country: Country code for results
            search_lang: Language code for results
            
        Returns:
            Dict with search results
        """
        if not self._enabled:
            raise ValueError("Brave Search API key not configured")
        
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key
        }
        
        params = {
            "q": query,
            "count": min(count, 20),
            "country": country,
            "search_lang": search_lang,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.BASE_URL,
                headers=headers,
                params=params
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Brave Search API error {response.status}: {error_text}")
                
                return await response.json()
    
    async def search_formatted(
        self,
        query: str,
        count: int = 5
    ) -> str:
        """
        Search and return formatted results for Claude/display.
        
        Returns:
            Formatted string with search results
        """
        try:
            results = await self.search(query, count)
            
            web_results = results.get("web", {}).get("results", [])
            
            if not web_results:
                return f"No results found for: {query}"
            
            formatted = [f"**Search results for: {query}**\n"]
            
            for i, result in enumerate(web_results, 1):
                title = result.get("title", "No title")
                url = result.get("url", "")
                description = result.get("description", "No description")
                
                formatted.append(f"{i}. **{title}**")
                formatted.append(f"   {url}")
                formatted.append(f"   {description}\n")
            
            return "\n".join(formatted)
            
        except Exception as e:
            return f"Search error: {str(e)}"
    
    def format_for_claude(self, results: dict) -> str:
        """
        Format search results as context for Claude.
        
        Returns:
            Formatted string suitable for system/user prompt
        """
        web_results = results.get("web", {}).get("results", [])
        
        if not web_results:
            return "No search results found."
        
        lines = ["Web search results:"]
        
        for i, result in enumerate(web_results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            description = result.get("description", "")
            
            lines.append(f"\n{i}. {title}")
            lines.append(f"   URL: {url}")
            if description:
                lines.append(f"   {description}")
        
        return "\n".join(lines)
    
    def search_sync(
        self,
        query: str,
        count: int = 5,
        country: str = "US",
        search_lang: str = "en"
    ) -> dict:
        """
        Search the web using Brave Search API (synchronous version).
        
        Use this in sync contexts (e.g., tool handlers).
        
        Args:
            query: Search query string
            count: Number of results (1-20)
            country: Country code for results
            search_lang: Language code for results
            
        Returns:
            Dict with search results
        """
        if not self._enabled:
            raise ValueError("Brave Search API key not configured")
        
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key
        }
        
        params = {
            "q": query,
            "count": min(count, 20),
            "country": country,
            "search_lang": search_lang,
        }
        
        response = requests.get(self.BASE_URL, headers=headers, params=params)
        
        if response.status_code != 200:
            raise Exception(f"Brave Search API error {response.status_code}: {response.text}")
        
        return response.json()
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """
        Get Claude tool definition for web search.
        
        Returns tool definition dict for Claude API.
        """
        return {
            "name": "web_search",
            "description": "Search the web for current information. Use when you need up-to-date information, facts, or details about recent events.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of results to return (1-10)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
