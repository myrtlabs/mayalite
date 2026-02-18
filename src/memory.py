"""
Memory and History Manager for MayaLite v0.4.

Handles:
- Appending to MEMORY.md with timestamps
- Saving/loading conversation history (JSONL)
- Memory compaction via Claude
- Per-user history for shared-dm mode
- Combined history for catchup feature
- Last document tracking (v0.4)
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional


class MemoryManager:
    """
    Manages memory persistence for a workspace.
    
    - MEMORY.md: Long-term notes (append-only with timestamps)
    - history.jsonl: Conversation history (JSON Lines format)
    - history_{user_id}.jsonl: Per-user history for shared-dm mode
    - last_document.json: Last processed document info (v0.4)
    """
    
    def __init__(self, workspace_path: Path, history_limit: int = 20):
        self.workspace_path = workspace_path.resolve()
        self.history_limit = history_limit
        
        # Ensure workspace exists
        self.workspace_path.mkdir(parents=True, exist_ok=True)
    
    def switch_workspace(self, new_workspace_path: Path) -> None:
        """Switch to a different workspace."""
        self.workspace_path = new_workspace_path.resolve()
        self.workspace_path.mkdir(parents=True, exist_ok=True)
    
    @property
    def memory_file(self) -> Path:
        return self.workspace_path / "MEMORY.md"
    
    @property
    def memory_backup_file(self) -> Path:
        return self.workspace_path / "MEMORY.md.bak"
    
    @property
    def history_file(self) -> Path:
        return self.workspace_path / "history.jsonl"
    
    @property
    def last_document_file(self) -> Path:
        return self.workspace_path / "last_document.json"
    
    def user_history_file(self, user_id: int) -> Path:
        """Get path to per-user history file."""
        return self.workspace_path / f"history_{user_id}.jsonl"
    
    def _safe_write(self, path: Path) -> bool:
        """Verify path is within workspace before writing."""
        resolved = path.resolve()
        return str(resolved).startswith(str(self.workspace_path))
    
    # ─────────────────────────────────────────────────────────────
    # MEMORY.md Operations
    # ─────────────────────────────────────────────────────────────
    
    def append_memory(self, content: str) -> bool:
        """Append a timestamped entry to MEMORY.md."""
        if not self._safe_write(self.memory_file):
            return False
        
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = f"\n## {timestamp}\n\n{content.strip()}\n\n---\n"
        
        with open(self.memory_file, "a", encoding="utf-8") as f:
            f.write(entry)
        
        return True
    
    def read_memory(self) -> Optional[str]:
        """Read the full MEMORY.md content."""
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return None
    
    def backup_memory(self) -> bool:
        """Create a backup of MEMORY.md."""
        if not self.memory_file.exists():
            return False
        
        try:
            shutil.copy2(self.memory_file, self.memory_backup_file)
            return True
        except Exception:
            return False
    
    def write_memory(self, content: str) -> bool:
        """Overwrite MEMORY.md with new content."""
        if not self._safe_write(self.memory_file):
            return False
        
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception:
            return False
    
    def restore_memory_from_backup(self) -> bool:
        """Restore MEMORY.md from backup."""
        if not self.memory_backup_file.exists():
            return False
        
        try:
            shutil.copy2(self.memory_backup_file, self.memory_file)
            return True
        except Exception:
            return False
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get stats about memory file."""
        if not self.memory_file.exists():
            return {"exists": False, "size_bytes": 0, "lines": 0}
        
        content = self.memory_file.read_text(encoding="utf-8")
        return {
            "exists": True,
            "size_bytes": self.memory_file.stat().st_size,
            "lines": len(content.splitlines()),
            "sections": content.count("## "),
        }
    
    # ─────────────────────────────────────────────────────────────
    # History (JSONL) Operations
    # ─────────────────────────────────────────────────────────────
    
    def append_turn(self, role: str, content: str, user_id: Optional[int] = None) -> bool:
        """Append a conversation turn to history."""
        if role not in ("user", "assistant"):
            return False
        
        if user_id is not None:
            target_file = self.user_history_file(user_id)
        else:
            target_file = self.history_file
        
        if not self._safe_write(target_file):
            return False
        
        entry = {
            "role": role,
            "content": content,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        
        if user_id is not None:
            entry["user_id"] = user_id
        
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        return True
    
    def load_history(
        self,
        limit: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Load recent conversation history."""
        if limit is None:
            limit = self.history_limit
        
        if user_id is not None:
            target_file = self.user_history_file(user_id)
        else:
            target_file = self.history_file
        
        if not target_file.exists():
            return []
        
        turns = []
        with open(target_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        turn = json.loads(line)
                        turns.append({
                            "role": turn["role"],
                            "content": turn["content"],
                        })
                    except json.JSONDecodeError:
                        continue
        
        return turns[-limit:] if limit else turns
    
    def clear_history(self, user_id: Optional[int] = None) -> bool:
        """Clear conversation history."""
        if user_id is not None:
            target_file = self.user_history_file(user_id)
        else:
            target_file = self.history_file
        
        if not self._safe_write(target_file):
            return False
        
        if target_file.exists():
            target_file.unlink()
        return True
    
    def get_history_stats(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get stats about conversation history."""
        if user_id is not None:
            target_file = self.user_history_file(user_id)
        else:
            target_file = self.history_file
        
        if not target_file.exists():
            return {"turns": 0, "size_bytes": 0}
        
        turns = 0
        with open(target_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    turns += 1
        
        return {
            "turns": turns,
            "size_bytes": target_file.stat().st_size,
        }
    
    # ─────────────────────────────────────────────────────────────
    # Shared-DM Mode - Combined History
    # ─────────────────────────────────────────────────────────────
    
    def load_other_users_history(
        self,
        current_user_id: int,
        authorized_users: List[int],
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Load history from other authorized users."""
        all_turns = []
        
        for user_id in authorized_users:
            if user_id == current_user_id:
                continue
            
            history_file = self.user_history_file(user_id)
            if not history_file.exists():
                continue
            
            with open(history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            turn = json.loads(line)
                            all_turns.append({
                                "role": turn["role"],
                                "content": turn["content"],
                                "user_id": turn.get("user_id", user_id),
                                "ts": turn.get("ts", ""),
                            })
                        except json.JSONDecodeError:
                            continue
        
        all_turns.sort(key=lambda x: x.get("ts", ""))
        return all_turns[-limit:] if limit else all_turns
    
    def get_catchup_summary_prompt(
        self,
        other_history: List[Dict[str, Any]],
        user_names: Optional[Dict[int, str]] = None,
    ) -> str:
        """Build a prompt for Claude to summarize other users' conversations."""
        if not other_history:
            return ""
        
        user_names = user_names or {}
        lines = ["Recent conversations from other workspace members:\n"]
        
        for turn in other_history:
            user_id = turn.get("user_id", "unknown")
            user_label = user_names.get(user_id, f"User {user_id}")
            ts = turn.get("ts", "")[:10]
            role = turn["role"]
            content = turn["content"][:500]
            
            if role == "user":
                lines.append(f"[{ts}] {user_label}: {content}")
            else:
                lines.append(f"[{ts}] Maya: {content}")
        
        lines.append("\n---")
        lines.append("Please provide a concise summary of what others discussed recently.")
        
        return "\n".join(lines)
    
    def list_user_history_files(self) -> List[int]:
        """List all user IDs that have history files."""
        user_ids = []
        for path in self.workspace_path.glob("history_*.jsonl"):
            try:
                user_id = int(path.stem.replace("history_", ""))
                user_ids.append(user_id)
            except ValueError:
                continue
        return sorted(user_ids)
    
    # ─────────────────────────────────────────────────────────────
    # v0.4: Last Document Tracking
    # ─────────────────────────────────────────────────────────────
    
    def save_last_document(
        self,
        filename: str,
        text: str,
        user_id: int,
    ) -> bool:
        """Save last processed document for /summarize command."""
        try:
            data = {
                "filename": filename,
                "text": text,
                "user_id": user_id,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            
            with open(self.last_document_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            
            return True
        except Exception:
            return False
    
    def get_last_document(self, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get last processed document."""
        if not self.last_document_file.exists():
            return None
        
        try:
            with open(self.last_document_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Optionally filter by user
            if user_id and data.get("user_id") != user_id:
                return None
            
            return data
        except Exception:
            return None
