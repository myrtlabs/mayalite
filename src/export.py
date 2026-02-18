"""
Export functionality for MayaLite v0.4.

Export memory, history, and full workspace as files.
"""

import json
import zipfile
import tempfile
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


class ExportManager:
    """
    Handles exporting workspace data as files.
    """
    
    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
    
    def export_memory(self) -> Optional[Path]:
        """
        Export MEMORY.md as a file.
        
        Returns:
            Path to exported file, or None if no memory exists
        """
        memory_file = self.workspace_path / "MEMORY.md"
        
        if not memory_file.exists():
            return None
        
        # Create temp file with proper name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_name = f"memory_{timestamp}.md"
        
        export_path = Path(tempfile.gettempdir()) / export_name
        
        # Copy content
        content = memory_file.read_text(encoding="utf-8")
        export_path.write_text(content, encoding="utf-8")
        
        return export_path
    
    def export_history(self, user_id: Optional[int] = None) -> Optional[Path]:
        """
        Export conversation history as a file.
        
        Args:
            user_id: If provided, exports user-specific history
            
        Returns:
            Path to exported file, or None if no history exists
        """
        if user_id:
            history_file = self.workspace_path / f"history_{user_id}.jsonl"
        else:
            history_file = self.workspace_path / "history.jsonl"
        
        if not history_file.exists():
            return None
        
        # Create human-readable export
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_name = f"history_{timestamp}.md"
        
        export_path = Path(tempfile.gettempdir()) / export_name
        
        # Convert JSONL to readable format
        lines = ["# Conversation History\n"]
        
        with open(history_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    entry = json.loads(line)
                    role = entry.get("role", "unknown")
                    content = entry.get("content", "")
                    ts = entry.get("ts", "")
                    
                    # Format timestamp
                    if ts:
                        try:
                            dt = datetime.fromisoformat(ts)
                            ts_str = dt.strftime("%Y-%m-%d %H:%M")
                        except Exception:
                            ts_str = ts[:16]
                    else:
                        ts_str = ""
                    
                    if role == "user":
                        lines.append(f"\n## User [{ts_str}]\n")
                    else:
                        lines.append(f"\n## Maya [{ts_str}]\n")
                    
                    lines.append(content)
                    lines.append("\n---")
                    
                except json.JSONDecodeError:
                    continue
        
        export_path.write_text("\n".join(lines), encoding="utf-8")
        
        return export_path
    
    def export_all(self) -> Optional[Path]:
        """
        Export full workspace as a zip file.
        
        Includes:
        - MEMORY.md
        - SOUL.md
        - TOOLS.md
        - HEARTBEAT.md
        - All history files
        - reminders.json
        - usage.json
        
        Returns:
            Path to exported zip file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        workspace_name = self.workspace_path.name
        export_name = f"workspace_{workspace_name}_{timestamp}.zip"
        
        export_path = Path(tempfile.gettempdir()) / export_name
        
        # Files to include
        include_patterns = [
            "MEMORY.md",
            "MEMORY.md.bak",
            "SOUL.md",
            "TOOLS.md",
            "HEARTBEAT.md",
            "history.jsonl",
            "history_*.jsonl",
            "reminders.json",
            "usage.json",
        ]
        
        files_found = []
        
        # Find matching files
        for pattern in include_patterns:
            if "*" in pattern:
                files_found.extend(self.workspace_path.glob(pattern))
            else:
                file_path = self.workspace_path / pattern
                if file_path.exists():
                    files_found.append(file_path)
        
        if not files_found:
            return None
        
        # Create zip file
        with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in files_found:
                arcname = file_path.name  # Just the filename
                zf.write(file_path, arcname)
        
        return export_path
    
    def list_exportable(self) -> dict:
        """
        List what's available for export.
        
        Returns:
            Dict with counts/info about exportable items
        """
        result = {
            "memory": False,
            "history_turns": 0,
            "soul": False,
            "tools": False,
            "heartbeat": False,
            "reminders": 0,
        }
        
        # Check files
        if (self.workspace_path / "MEMORY.md").exists():
            result["memory"] = True
        
        if (self.workspace_path / "SOUL.md").exists():
            result["soul"] = True
        
        if (self.workspace_path / "TOOLS.md").exists():
            result["tools"] = True
        
        if (self.workspace_path / "HEARTBEAT.md").exists():
            result["heartbeat"] = True
        
        # Count history turns
        history_file = self.workspace_path / "history.jsonl"
        if history_file.exists():
            with open(history_file, "r") as f:
                result["history_turns"] = sum(1 for line in f if line.strip())
        
        # Count reminders
        reminders_file = self.workspace_path / "reminders.json"
        if reminders_file.exists():
            try:
                with open(reminders_file, "r") as f:
                    data = json.load(f)
                    result["reminders"] = len(data)
            except Exception:
                pass
        
        return result
