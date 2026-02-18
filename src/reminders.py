"""
Reminder system for MayaLite v0.4.

Natural language reminder parsing and scheduling.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, asdict

import dateparser
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)


@dataclass
class Reminder:
    """A scheduled reminder."""
    id: str
    user_id: int
    chat_id: int
    message: str
    trigger_time: str  # ISO format
    created_at: str  # ISO format
    workspace: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reminder":
        return cls(**data)


class ReminderManager:
    """
    Manages reminders with natural language parsing.
    
    Stores reminders in workspace/reminders.json for persistence.
    """
    
    def __init__(
        self,
        workspace_path: Path,
        scheduler: AsyncIOScheduler,
        send_callback: Callable,
    ):
        self.workspace_path = workspace_path
        self.scheduler = scheduler
        self.send_callback = send_callback
        self._reminders: Dict[str, Reminder] = {}
        
        # Load existing reminders
        self._load_reminders()
        self._schedule_pending()
    
    @property
    def reminders_file(self) -> Path:
        return self.workspace_path / "reminders.json"
    
    def _load_reminders(self) -> None:
        """Load reminders from file."""
        if not self.reminders_file.exists():
            return
        
        try:
            with open(self.reminders_file, "r") as f:
                data = json.load(f)
            
            for reminder_data in data:
                reminder = Reminder.from_dict(reminder_data)
                self._reminders[reminder.id] = reminder
                
        except Exception as e:
            logger.error(f"Error loading reminders: {e}")
    
    def _save_reminders(self) -> None:
        """Save reminders to file."""
        try:
            self.workspace_path.mkdir(parents=True, exist_ok=True)
            
            data = [r.to_dict() for r in self._reminders.values()]
            
            with open(self.reminders_file, "w") as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving reminders: {e}")
    
    def _schedule_pending(self) -> None:
        """Schedule all pending reminders."""
        now = datetime.now(timezone.utc)
        
        for reminder in list(self._reminders.values()):
            trigger_time = datetime.fromisoformat(reminder.trigger_time)
            
            if trigger_time <= now:
                # Already past - remove it
                del self._reminders[reminder.id]
            else:
                # Schedule it
                self._schedule_reminder(reminder)
        
        self._save_reminders()
    
    def _schedule_reminder(self, reminder: Reminder) -> None:
        """Schedule a single reminder."""
        trigger_time = datetime.fromisoformat(reminder.trigger_time)
        
        self.scheduler.add_job(
            self._trigger_reminder,
            trigger=DateTrigger(run_date=trigger_time),
            id=f"reminder_{reminder.id}",
            args=[reminder.id],
            replace_existing=True,
            max_instances=1,
        )
    
    async def _trigger_reminder(self, reminder_id: str) -> None:
        """Called when a reminder triggers."""
        reminder = self._reminders.get(reminder_id)
        
        if not reminder:
            return
        
        try:
            # Send the reminder
            message = f"⏰ **Reminder**\n\n{reminder.message}"
            await self.send_callback(reminder.chat_id, message)
            
        except Exception as e:
            logger.error(f"Error sending reminder: {e}")
        
        finally:
            # Remove from storage
            if reminder_id in self._reminders:
                del self._reminders[reminder_id]
                self._save_reminders()
    
    def parse_time(self, time_str: str) -> Optional[datetime]:
        """
        Parse natural language time string.
        
        Examples:
        - "in 2 hours"
        - "tomorrow at 9am"
        - "in 30 minutes"
        - "next monday at 3pm"
        
        Returns:
            Parsed datetime or None if parsing fails
        """
        settings = {
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": True,
        }
        
        parsed = dateparser.parse(time_str, settings=settings)
        
        if parsed:
            # Ensure it's in the future
            now = datetime.now(timezone.utc)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            
            if parsed > now:
                return parsed
        
        return None
    
    def create_reminder(
        self,
        user_id: int,
        chat_id: int,
        time_str: str,
        message: str,
        workspace: str,
    ) -> Optional[Reminder]:
        """
        Create a new reminder.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID for delivery
            time_str: Natural language time (e.g., "in 2 hours")
            message: Reminder message
            workspace: Current workspace name
            
        Returns:
            Created Reminder or None if time parsing fails
        """
        trigger_time = self.parse_time(time_str)
        
        if not trigger_time:
            return None
        
        # Generate unique ID
        import uuid
        reminder_id = str(uuid.uuid4())[:8]
        
        reminder = Reminder(
            id=reminder_id,
            user_id=user_id,
            chat_id=chat_id,
            message=message,
            trigger_time=trigger_time.isoformat(),
            created_at=datetime.now(timezone.utc).isoformat(),
            workspace=workspace,
        )
        
        self._reminders[reminder_id] = reminder
        self._schedule_reminder(reminder)
        self._save_reminders()
        
        return reminder
    
    def list_reminders(
        self,
        user_id: Optional[int] = None,
        workspace: Optional[str] = None,
    ) -> List[Reminder]:
        """
        List pending reminders.
        
        Args:
            user_id: Filter by user ID (optional)
            workspace: Filter by workspace (optional)
            
        Returns:
            List of pending Reminder objects
        """
        now = datetime.now(timezone.utc)
        reminders = []
        
        for reminder in self._reminders.values():
            # Filter by user if specified
            if user_id and reminder.user_id != user_id:
                continue
            
            # Filter by workspace if specified
            if workspace and reminder.workspace != workspace:
                continue
            
            # Check if still pending
            trigger_time = datetime.fromisoformat(reminder.trigger_time)
            if trigger_time > now:
                reminders.append(reminder)
        
        # Sort by trigger time
        reminders.sort(key=lambda r: r.trigger_time)
        
        return reminders
    
    def cancel_reminder(self, reminder_id: str) -> bool:
        """
        Cancel a reminder.
        
        Returns:
            True if cancelled, False if not found
        """
        if reminder_id not in self._reminders:
            return False
        
        # Remove from scheduler
        try:
            self.scheduler.remove_job(f"reminder_{reminder_id}")
        except Exception:
            pass
        
        # Remove from storage
        del self._reminders[reminder_id]
        self._save_reminders()
        
        return True
    
    def format_reminder_list(self, reminders: List[Reminder]) -> str:
        """Format reminders for display."""
        if not reminders:
            return "📭 No pending reminders."
        
        lines = ["⏰ **Pending Reminders**\n"]
        
        for r in reminders:
            trigger = datetime.fromisoformat(r.trigger_time)
            time_str = trigger.strftime("%Y-%m-%d %H:%M %Z")
            lines.append(f"• `{r.id}`: {r.message[:50]}")
            lines.append(f"  ⏱ {time_str}")
        
        return "\n".join(lines)
