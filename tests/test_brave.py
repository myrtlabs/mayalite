"""Tests for Brave Search client."""

import pytest

from src.brave import BraveSearchClient


def test_client_disabled_without_key():
    """Test client is disabled without API key."""
    client = BraveSearchClient("")
    
    assert client.enabled is False


def test_client_enabled_with_key():
    """Test client is enabled with API key."""
    client = BraveSearchClient("test-api-key")
    
    assert client.enabled is True


def test_search_sync_raises_without_key():
    """Test sync search raises error without API key."""
    client = BraveSearchClient("")
    
    with pytest.raises(ValueError, match="not configured"):
        client.search_sync("test query")


def test_format_for_claude_empty():
    """Test formatting empty results."""
    client = BraveSearchClient("test-key")
    
    result = client.format_for_claude({})
    
    assert "No search results" in result


def test_format_for_claude_with_results():
    """Test formatting results for Claude."""
    client = BraveSearchClient("test-key")
    
    results = {
        "web": {
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "description": "A test description",
                },
                {
                    "title": "Another Result",
                    "url": "https://example.org",
                    "description": "Another description",
                },
            ]
        }
    }
    
    formatted = client.format_for_claude(results)
    
    assert "Test Result" in formatted
    assert "https://example.com" in formatted
    assert "Another Result" in formatted


def test_tool_definition():
    """Test tool definition for Claude."""
    client = BraveSearchClient("test-key")
    
    tool_def = client.get_tool_definition()
    
    assert tool_def["name"] == "web_search"
    assert "description" in tool_def
    assert "input_schema" in tool_def
    assert tool_def["input_schema"]["properties"]["query"]["type"] == "string"
