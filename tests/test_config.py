"""Tests for configuration loading."""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.config import load_config, Config


@pytest.fixture
def temp_config():
    """Create temporary config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {
            "telegram": {
                "token": "test-token-123",
                "authorized_users": [12345, 67890],
                "alert_chat_id": 12345,
            },
            "claude": {
                "api_key": "sk-ant-test",
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4096,
            },
            "workspaces": {
                "default": "main",
                "history_limit": 20,
                "configs": {
                    "main": {"mode": "single"},
                    "team": {
                        "mode": "shared-dm",
                        "authorized_users": [12345, 67890],
                    },
                },
            },
            "heartbeat": {
                "enabled": True,
                "interval_minutes": 30,
            },
        }
        yaml.dump(config, f)
        yield Path(f.name)


def test_load_config(temp_config):
    """Test loading valid config."""
    config = load_config(temp_config)
    
    assert isinstance(config, Config)
    assert config.telegram.token == "test-token-123"
    assert 12345 in config.telegram.authorized_users
    assert config.claude.api_key == "sk-ant-test"


def test_config_telegram_section(temp_config):
    """Test Telegram config section."""
    config = load_config(temp_config)
    
    assert config.telegram.token == "test-token-123"
    assert len(config.telegram.authorized_users) == 2
    assert config.telegram.alert_chat_id == 12345


def test_config_claude_section(temp_config):
    """Test Claude config section."""
    config = load_config(temp_config)
    
    assert config.claude.api_key == "sk-ant-test"
    assert "claude" in config.claude.model
    assert config.claude.max_tokens == 4096


def test_config_workspaces_section(temp_config):
    """Test workspaces config section."""
    config = load_config(temp_config)
    
    assert config.workspaces.default == "main"
    assert config.workspaces.history_limit == 20
    assert "main" in config.workspaces.configs
    assert "team" in config.workspaces.configs


def test_config_workspace_modes(temp_config):
    """Test workspace mode configuration."""
    config = load_config(temp_config)
    
    main_config = config.workspaces.configs["main"]
    team_config = config.workspaces.configs["team"]
    
    assert main_config.mode == "single"
    assert team_config.mode == "shared-dm"
    assert 12345 in team_config.authorized_users


def test_config_heartbeat(temp_config):
    """Test heartbeat configuration."""
    config = load_config(temp_config)
    
    assert config.heartbeat.enabled is True
    assert config.heartbeat.interval_minutes == 30


def test_config_missing_file():
    """Test loading missing config file."""
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/config.yaml"))


def test_config_optional_sections(temp_config):
    """Test optional config sections have defaults."""
    config = load_config(temp_config)
    
    # Brave should have defaults
    assert config.brave.api_key == ""
    assert config.brave.enabled is False
    
    # OpenAI should have defaults
    assert config.openai.api_key == ""
    assert config.openai.enabled is False
    
    # Digest should have defaults
    assert config.digest.enabled is False


def test_config_models_aliases(temp_config):
    """Test model aliases configuration."""
    config = load_config(temp_config)
    
    # Should have default aliases
    assert "sonnet" in config.models.aliases
    assert "opus" in config.models.aliases
