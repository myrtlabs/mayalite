"""
Configuration loader for MayaLite v0.4.

v0.4 additions:
- Brave Search config
- OpenAI (Whisper) config
- Model aliases for multi-model support
- Daily digest configuration
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

import yaml


@dataclass
class TelegramConfig:
    token: str
    authorized_users: List[int]
    alert_chat_id: Optional[int] = None  # For heartbeat alerts


@dataclass
class ClaudeConfig:
    api_key: str
    model: str
    max_tokens: int


@dataclass
class BraveConfig:
    """Brave Search API configuration."""
    api_key: str = ""
    enabled: bool = False


@dataclass
class OpenAIConfig:
    """OpenAI API configuration (for Whisper)."""
    api_key: str = ""
    whisper_model: str = "whisper-1"
    enabled: bool = False


@dataclass
class ModelsConfig:
    """Multi-model configuration."""
    default: str = "claude-sonnet-4-20250514"
    aliases: Dict[str, str] = field(default_factory=lambda: {
        "sonnet": "claude-sonnet-4-20250514",
        "opus": "claude-opus-4-20250514",
        "haiku": "claude-3-5-haiku-20241022",
    })


@dataclass
class DigestConfig:
    """Daily digest configuration."""
    enabled: bool = False
    time: str = "08:00"
    timezone: str = "America/New_York"
    location: str = ""  # For weather


@dataclass
class WorkspaceConfigEntry:
    """Configuration for a single workspace."""
    mode: str = "single"  # "single", "shared-dm", "group"
    authorized_users: List[int] = field(default_factory=list)
    telegram_group_id: Optional[int] = None
    listen_mode: str = "all"  # "all" or "mentions"
    model: Optional[str] = None  # Override model for this workspace


@dataclass
class WorkspacesConfig:
    default: str
    history_limit: int
    configs: Dict[str, WorkspaceConfigEntry] = field(default_factory=dict)


@dataclass
class HeartbeatConfig:
    enabled: bool = False
    interval_minutes: int = 30
    compact_enabled: bool = False
    compact_cron: str = "0 3 * * *"  # 3am daily by default


@dataclass
class Config:
    telegram: TelegramConfig
    claude: ClaudeConfig
    workspaces: WorkspacesConfig
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)
    brave: BraveConfig = field(default_factory=BraveConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    digest: DigestConfig = field(default_factory=DigestConfig)


def _parse_workspace_configs(data: dict) -> Dict[str, WorkspaceConfigEntry]:
    """Parse workspace configurations from YAML data."""
    configs = {}
    configs_data = data.get("configs", {})
    
    for name, ws_config in configs_data.items():
        if ws_config is None:
            ws_config = {}
        
        configs[name] = WorkspaceConfigEntry(
            mode=ws_config.get("mode", "single"),
            authorized_users=ws_config.get("authorized_users", []),
            telegram_group_id=ws_config.get("telegram_group_id"),
            listen_mode=ws_config.get("listen_mode", "all"),
            model=ws_config.get("model"),
        )
    
    return configs


def load_config(config_path: Optional[Path] = None) -> Config:
    """
    Load configuration from YAML file.
    
    Priority:
    1. Explicit config_path argument
    2. MAYALITE_CONFIG environment variable
    3. config.yaml in project root
    """
    if config_path is None:
        env_path = os.environ.get("MAYALITE_CONFIG")
        if env_path:
            config_path = Path(env_path)
        else:
            # Default to config.yaml in project root
            config_path = Path(__file__).parent.parent / "config.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            "Copy config.yaml.example to config.yaml and fill in your values."
        )
    
    with open(config_path, "r") as f:
        data = yaml.safe_load(f)
    
    # Parse heartbeat config with defaults
    heartbeat_data = data.get("heartbeat", {})
    heartbeat_config = HeartbeatConfig(
        enabled=heartbeat_data.get("enabled", False),
        interval_minutes=heartbeat_data.get("interval_minutes", 30),
        compact_enabled=heartbeat_data.get("compact_enabled", False),
        compact_cron=heartbeat_data.get("compact_cron", "0 3 * * *"),
    )
    
    # Parse workspaces config
    workspaces_data = data.get("workspaces", {})
    workspace_configs = _parse_workspace_configs(workspaces_data)
    
    # Parse brave config
    brave_data = data.get("brave", {})
    brave_config = BraveConfig(
        api_key=brave_data.get("api_key", ""),
        enabled=bool(brave_data.get("api_key")),
    )
    
    # Parse openai config
    openai_data = data.get("openai", {})
    openai_config = OpenAIConfig(
        api_key=openai_data.get("api_key", ""),
        whisper_model=openai_data.get("whisper_model", "whisper-1"),
        enabled=bool(openai_data.get("api_key")),
    )
    
    # Parse models config
    models_data = data.get("models", {})
    models_config = ModelsConfig(
        default=models_data.get("default", "claude-sonnet-4-20250514"),
        aliases=models_data.get("aliases", {
            "sonnet": "claude-sonnet-4-20250514",
            "opus": "claude-opus-4-20250514",
            "haiku": "claude-3-5-haiku-20241022",
        }),
    )
    
    # Parse digest config
    digest_data = data.get("digest", {})
    digest_config = DigestConfig(
        enabled=digest_data.get("enabled", False),
        time=digest_data.get("time", "08:00"),
        timezone=digest_data.get("timezone", "America/New_York"),
        location=digest_data.get("location", ""),
    )
    
    return Config(
        telegram=TelegramConfig(
            token=data["telegram"]["token"],
            authorized_users=data["telegram"]["authorized_users"],
            alert_chat_id=data["telegram"].get("alert_chat_id"),
        ),
        claude=ClaudeConfig(
            api_key=data["claude"]["api_key"],
            model=data["claude"]["model"],
            max_tokens=data["claude"]["max_tokens"],
        ),
        workspaces=WorkspacesConfig(
            default=workspaces_data.get("default", "main"),
            history_limit=workspaces_data.get("history_limit", 20),
            configs=workspace_configs,
        ),
        heartbeat=heartbeat_config,
        brave=brave_config,
        openai=openai_config,
        models=models_config,
        digest=digest_config,
    )
