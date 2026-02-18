"""Tests for memory management."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.memory import MemoryManager


@pytest.fixture
def temp_workspace():
    """Create temporary workspace with memory files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        
        # Create MEMORY.md
        (ws / "MEMORY.md").write_text(
            "# Memory\n\n## Section 1\n- Item A\n- Item B\n"
        )
        
        # Create empty history
        (ws / "history.jsonl").write_text("")
        
        yield ws


def test_memory_manager_init(temp_workspace):
    """Test MemoryManager initialization."""
    manager = MemoryManager(temp_workspace, history_limit=20)
    
    assert manager.workspace_path == temp_workspace
    assert manager.history_limit == 20


def test_read_memory(temp_workspace):
    """Test reading MEMORY.md."""
    manager = MemoryManager(temp_workspace)
    
    content = manager.read_memory()
    
    assert "# Memory" in content
    assert "Item A" in content
    assert "Item B" in content


def test_read_memory_missing(temp_workspace):
    """Test reading missing MEMORY.md."""
    (temp_workspace / "MEMORY.md").unlink()
    manager = MemoryManager(temp_workspace)
    
    content = manager.read_memory()
    
    assert content == ""


def test_append_memory(temp_workspace):
    """Test appending to MEMORY.md."""
    manager = MemoryManager(temp_workspace)
    
    result = manager.append_memory("New item to remember")
    
    assert result is True
    content = (temp_workspace / "MEMORY.md").read_text()
    assert "New item to remember" in content


def test_append_turn(temp_workspace):
    """Test appending conversation turns."""
    manager = MemoryManager(temp_workspace)
    
    manager.append_turn("user", "Hello")
    manager.append_turn("assistant", "Hi there!")
    
    history = manager.load_history()
    
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Hi there!"


def test_history_limit(temp_workspace):
    """Test history respects limit."""
    manager = MemoryManager(temp_workspace, history_limit=3)
    
    # Add 5 turns
    for i in range(5):
        manager.append_turn("user", f"Message {i}")
    
    history = manager.load_history()
    
    # Should only get last 3
    assert len(history) == 3
    assert history[0]["content"] == "Message 2"
    assert history[2]["content"] == "Message 4"


def test_clear_history(temp_workspace):
    """Test clearing history."""
    manager = MemoryManager(temp_workspace)
    
    manager.append_turn("user", "Hello")
    manager.append_turn("assistant", "Hi")
    
    manager.clear_history()
    
    history = manager.load_history()
    assert len(history) == 0


def test_get_memory_stats(temp_workspace):
    """Test memory statistics."""
    manager = MemoryManager(temp_workspace)
    
    stats = manager.get_memory_stats()
    
    assert "sections" in stats or stats == {}


def test_get_history_stats(temp_workspace):
    """Test history statistics."""
    manager = MemoryManager(temp_workspace)
    
    manager.append_turn("user", "Hello")
    manager.append_turn("assistant", "Hi")
    
    stats = manager.get_history_stats()
    
    assert stats["turns"] == 2


def test_per_user_history(temp_workspace):
    """Test per-user history for shared-dm mode."""
    manager = MemoryManager(temp_workspace)
    
    # User 1
    manager.append_turn("user", "Hello from user 1", user_id=111)
    manager.append_turn("assistant", "Hi user 1", user_id=111)
    
    # User 2
    manager.append_turn("user", "Hello from user 2", user_id=222)
    manager.append_turn("assistant", "Hi user 2", user_id=222)
    
    # Load per-user
    history_1 = manager.load_history(user_id=111)
    history_2 = manager.load_history(user_id=222)
    
    assert len(history_1) == 2
    assert len(history_2) == 2
    assert "user 1" in history_1[0]["content"]
    assert "user 2" in history_2[0]["content"]
