"""Tests for workspace management."""

import tempfile
from pathlib import Path

import pytest

from src.workspace import WorkspaceManager
from src.config import WorkspacesConfig, WorkspaceConfigEntry


@pytest.fixture
def temp_workspaces():
    """Create temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        
        # Create _global
        (base / "_global").mkdir()
        (base / "_global" / "IDENTITY.md").write_text("# Test Identity")
        (base / "_global" / "USER.md").write_text("# Test User")
        
        # Create main workspace
        (base / "main").mkdir()
        (base / "main" / "SOUL.md").write_text("# Main Soul")
        (base / "main" / "MEMORY.md").write_text("# Main Memory")
        
        # Create test workspace
        (base / "test").mkdir()
        (base / "test" / "SOUL.md").write_text("# Test Soul")
        
        yield base


def test_workspace_exists(temp_workspaces):
    """Test workspace existence check."""
    manager = WorkspaceManager(temp_workspaces)
    
    assert manager.workspace_exists("main")
    assert manager.workspace_exists("test")
    assert not manager.workspace_exists("nonexistent")
    assert not manager.workspace_exists("_global")  # Hidden


def test_workspace_switch(temp_workspaces):
    """Test switching workspaces."""
    manager = WorkspaceManager(temp_workspaces, default_workspace="main")
    
    assert manager.current == "main"
    
    assert manager.switch("test")
    assert manager.current == "test"
    
    assert not manager.switch("nonexistent")
    assert manager.current == "test"  # Unchanged


def test_list_workspaces(temp_workspaces):
    """Test listing available workspaces."""
    manager = WorkspaceManager(temp_workspaces)
    
    workspaces = manager.list_workspaces()
    
    assert "main" in workspaces
    assert "test" in workspaces
    assert "_global" not in workspaces


def test_load_context(temp_workspaces):
    """Test context loading."""
    manager = WorkspaceManager(temp_workspaces, default_workspace="main")
    
    context = manager.load_context()
    
    assert "Test Identity" in context
    assert "Test User" in context
    assert "Main Soul" in context
    assert "Main Memory" in context


def test_safe_path_traversal(temp_workspaces):
    """Test path traversal protection."""
    manager = WorkspaceManager(temp_workspaces)
    
    with pytest.raises(ValueError, match="Path traversal"):
        manager._safe_path("../../../etc/passwd")
