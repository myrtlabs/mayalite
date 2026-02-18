"""
Workspace Manager for MayaLite v0.4.

v0.4 additions:
- Per-workspace model configuration
"""

from pathlib import Path
from typing import Optional, List, Dict

from .config import WorkspacesConfig, WorkspaceConfigEntry


class WorkspaceManager:
    """
    Manages workspace context and file access.
    
    Security: Only allows access to files within the workspaces directory.
    """
    
    def __init__(
        self,
        base_path: Path,
        default_workspace: str = "main",
        workspaces_config: Optional[WorkspacesConfig] = None,
    ):
        self.base_path = base_path.resolve()
        self.current = default_workspace
        self._config = workspaces_config
        
        # Build reverse lookup: group_id -> workspace_name
        self._group_to_workspace: Dict[int, str] = {}
        if self._config:
            for ws_name, ws_cfg in self._config.configs.items():
                if ws_cfg.mode == "group" and ws_cfg.telegram_group_id:
                    self._group_to_workspace[ws_cfg.telegram_group_id] = ws_name
        
        # Ensure directories exist
        self._ensure_workspace_exists(default_workspace)
        self._ensure_global_exists()
    
    def _ensure_workspace_exists(self, name: str) -> None:
        """Create workspace directory if it doesn't exist."""
        ws_path = self.base_path / name
        ws_path.mkdir(parents=True, exist_ok=True)
    
    def _ensure_global_exists(self) -> None:
        """Create _global directory if it doesn't exist."""
        global_path = self.base_path / "_global"
        global_path.mkdir(parents=True, exist_ok=True)
    
    def _safe_path(self, relative_path: str) -> Path:
        """Resolve a path and ensure it's within workspaces directory."""
        full_path = (self.base_path / relative_path).resolve()
        
        if not str(full_path).startswith(str(self.base_path)):
            raise ValueError(f"Path traversal detected: {relative_path}")
        
        return full_path
    
    def _read_file_safe(self, relative_path: str) -> Optional[str]:
        """Safely read a file within the workspace directory."""
        try:
            path = self._safe_path(relative_path)
            if path.exists() and path.is_file():
                return path.read_text(encoding="utf-8")
        except (ValueError, PermissionError):
            pass
        return None
    
    def _get_workspace_config(self, workspace: str) -> WorkspaceConfigEntry:
        """Get configuration for a workspace."""
        if self._config and workspace in self._config.configs:
            return self._config.configs[workspace]
        return WorkspaceConfigEntry()
    
    # ─────────────────────────────────────────────────────────────
    # Workspace Mode & Authorization
    # ─────────────────────────────────────────────────────────────
    
    def get_workspace_mode(self, workspace_name: Optional[str] = None) -> str:
        """Get the mode for a workspace."""
        ws = workspace_name or self.current
        config = self._get_workspace_config(ws)
        return config.mode
    
    def get_workspace_model(self, workspace_name: Optional[str] = None) -> Optional[str]:
        """Get the model override for a workspace (v0.4)."""
        ws = workspace_name or self.current
        config = self._get_workspace_config(ws)
        return config.model
    
    def is_user_authorized(self, workspace_name: str, user_id: int) -> bool:
        """Check if a user is authorized for a workspace."""
        config = self._get_workspace_config(workspace_name)
        
        if config.mode == "single":
            return True
        
        if config.mode == "shared-dm":
            return user_id in config.authorized_users
        
        if config.mode == "group":
            return True
        
        return False
    
    def get_group_id(self, workspace_name: Optional[str] = None) -> Optional[int]:
        """Get the Telegram group ID for a group-mode workspace."""
        ws = workspace_name or self.current
        config = self._get_workspace_config(ws)
        return config.telegram_group_id if config.mode == "group" else None
    
    def get_listen_mode(self, workspace_name: Optional[str] = None) -> str:
        """Get the listen mode for a group workspace."""
        ws = workspace_name or self.current
        config = self._get_workspace_config(ws)
        return config.listen_mode
    
    def get_workspace_for_group(self, group_id: int) -> Optional[str]:
        """Get workspace name for a given Telegram group ID."""
        return self._group_to_workspace.get(group_id)
    
    def get_authorized_workspaces(self, user_id: int) -> List[str]:
        """Get list of workspaces a user is authorized to access."""
        authorized = []
        all_workspaces = self.list_workspaces()
        
        for ws in all_workspaces:
            config = self._get_workspace_config(ws)
            
            if config.mode == "single":
                authorized.append(ws)
            elif config.mode == "shared-dm":
                if user_id in config.authorized_users:
                    authorized.append(ws)
        
        return sorted(authorized)
    
    def get_workspace_authorized_users(self, workspace_name: Optional[str] = None) -> List[int]:
        """Get list of authorized users for a shared-dm workspace."""
        ws = workspace_name or self.current
        config = self._get_workspace_config(ws)
        return config.authorized_users if config.mode == "shared-dm" else []
    
    # ─────────────────────────────────────────────────────────────
    # Core Workspace Operations
    # ─────────────────────────────────────────────────────────────
    
    def get_workspace_path(self, workspace: Optional[str] = None) -> Path:
        """Get the path to current or specified workspace."""
        ws = workspace or self.current
        return self._safe_path(ws)
    
    def load_context(self) -> str:
        """Build the full system context for Claude."""
        parts = []
        ws = self.current
        
        # Global identity files
        identity = self._read_file_safe("_global/IDENTITY.md")
        if identity:
            parts.append(f"# Identity\n\n{identity}")
        
        user = self._read_file_safe("_global/USER.md")
        if user:
            parts.append(f"# About the User\n\n{user}")
        
        # Workspace-specific files
        soul = self._read_file_safe(f"{ws}/SOUL.md")
        if soul:
            parts.append(f"# Workspace Context: {ws}\n\n{soul}")
        
        memory = self._read_file_safe(f"{ws}/MEMORY.md")
        if memory:
            parts.append(f"# Memory\n\n{memory}")
        
        tools = self._read_file_safe(f"{ws}/TOOLS.md")
        if tools:
            parts.append(f"# Tools & References\n\n{tools}")
        
        if not parts:
            return "You are Maya, a helpful AI assistant."
        
        return "\n\n---\n\n".join(parts)
    
    def load_heartbeat_prompt(self) -> Optional[str]:
        """Load HEARTBEAT.md from current workspace if it exists."""
        return self._read_file_safe(f"{self.current}/HEARTBEAT.md")
    
    def list_workspaces(self) -> List[str]:
        """List available workspaces."""
        workspaces = []
        for path in self.base_path.iterdir():
            if path.is_dir() and not path.name.startswith("_"):
                workspaces.append(path.name)
        return sorted(workspaces)
    
    def workspace_exists(self, name: str) -> bool:
        """Check if a workspace exists."""
        if name.startswith("_"):
            return False
        ws_path = self.base_path / name
        return ws_path.exists() and ws_path.is_dir()
    
    def switch(self, name: str) -> bool:
        """Switch to a different workspace."""
        if self.workspace_exists(name):
            self.current = name
            return True
        return False
    
    def get_workspace_info(self, name: Optional[str] = None) -> dict:
        """Get information about a workspace."""
        ws = name or self.current
        config = self._get_workspace_config(ws)
        
        return {
            "name": ws,
            "mode": config.mode,
            "model": config.model,
            "has_soul": self._read_file_safe(f"{ws}/SOUL.md") is not None,
            "has_memory": self._read_file_safe(f"{ws}/MEMORY.md") is not None,
            "has_tools": self._read_file_safe(f"{ws}/TOOLS.md") is not None,
            "has_heartbeat": self._read_file_safe(f"{ws}/HEARTBEAT.md") is not None,
        }
