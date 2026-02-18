"""
Daily digest for MayaLite v0.4.

Sends a configurable daily summary at specified time.
"""

import logging
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import DigestConfig
from .reminders import ReminderManager

logger = logging.getLogger(__name__)


class DigestManager:
    """
    Manages daily digest summaries.
    
    Includes:
    - Weather (if location set)
    - Pending reminders
    - Memory highlights
    """
    
    # OpenWeatherMap API (free tier)
    WEATHER_API = "https://api.openweathermap.org/data/2.5/weather"
    
    def __init__(
        self,
        config: DigestConfig,
        scheduler: AsyncIOScheduler,
        send_callback: Callable,
        reminder_manager: Optional[ReminderManager] = None,
        memory_reader: Optional[Callable] = None,
        weather_api_key: Optional[str] = None,
    ):
        self.config = config
        self.scheduler = scheduler
        self.send_callback = send_callback
        self.reminder_manager = reminder_manager
        self.memory_reader = memory_reader
        self.weather_api_key = weather_api_key
        
        self._chat_ids: List[int] = []
        
        if config.enabled:
            self._setup_schedule()
    
    def _setup_schedule(self) -> None:
        """Set up the daily digest schedule."""
        # Parse time
        try:
            hour, minute = self.config.time.split(":")
            hour = int(hour)
            minute = int(minute)
        except Exception:
            hour, minute = 8, 0
        
        self.scheduler.add_job(
            self._send_digest,
            trigger=CronTrigger(
                hour=hour,
                minute=minute,
                timezone=self.config.timezone,
            ),
            id="daily_digest",
            name="Daily Digest",
            replace_existing=True,
            max_instances=1,
        )
        
        logger.info(f"Daily digest scheduled for {hour:02d}:{minute:02d} {self.config.timezone}")
    
    def add_recipient(self, chat_id: int) -> None:
        """Add a chat ID to receive daily digests."""
        if chat_id not in self._chat_ids:
            self._chat_ids.append(chat_id)
    
    def remove_recipient(self, chat_id: int) -> None:
        """Remove a chat ID from daily digests."""
        if chat_id in self._chat_ids:
            self._chat_ids.remove(chat_id)
    
    async def _get_weather(self) -> Optional[str]:
        """Fetch current weather for configured location."""
        if not self.config.location or not self.weather_api_key:
            return None
        
        try:
            params = {
                "q": self.config.location,
                "appid": self.weather_api_key,
                "units": "imperial",  # Fahrenheit
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.WEATHER_API, params=params) as resp:
                    if resp.status != 200:
                        return None
                    
                    data = await resp.json()
            
            # Format weather
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            desc = data["weather"][0]["description"].title()
            humidity = data["main"]["humidity"]
            
            return (
                f"🌤 **Weather in {self.config.location}**\n"
                f"  {desc}, {temp:.0f}°F (feels like {feels_like:.0f}°F)\n"
                f"  Humidity: {humidity}%"
            )
            
        except Exception as e:
            logger.error(f"Weather fetch error: {e}")
            return None
    
    async def _get_reminders_summary(self) -> Optional[str]:
        """Get summary of pending reminders."""
        if not self.reminder_manager:
            return None
        
        reminders = self.reminder_manager.list_reminders()
        
        if not reminders:
            return None
        
        lines = [f"⏰ **{len(reminders)} Pending Reminder(s)**"]
        
        for r in reminders[:5]:  # Show max 5
            trigger = datetime.fromisoformat(r.trigger_time)
            time_str = trigger.strftime("%H:%M")
            lines.append(f"  • {time_str}: {r.message[:40]}")
        
        if len(reminders) > 5:
            lines.append(f"  ... and {len(reminders) - 5} more")
        
        return "\n".join(lines)
    
    async def _get_memory_highlights(self) -> Optional[str]:
        """Get recent memory highlights."""
        if not self.memory_reader:
            return None
        
        try:
            memory = self.memory_reader()
            
            if not memory:
                return None
            
            # Get last section from memory
            sections = memory.split("## ")
            
            if len(sections) < 2:
                return None
            
            # Get most recent section
            latest = sections[-1]
            
            # Truncate if needed
            if len(latest) > 200:
                latest = latest[:200] + "..."
            
            return f"📝 **Recent Memory**\n  {latest.strip()}"
            
        except Exception as e:
            logger.error(f"Memory read error: {e}")
            return None
    
    async def _build_digest(self) -> str:
        """Build the daily digest message."""
        now = datetime.now()
        parts = [f"☀️ **Good Morning!**\n_{now.strftime('%A, %B %d, %Y')}_\n"]
        
        # Weather
        weather = await self._get_weather()
        if weather:
            parts.append(weather)
        
        # Reminders
        reminders = await self._get_reminders_summary()
        if reminders:
            parts.append(reminders)
        
        # Memory highlights
        memory = await self._get_memory_highlights()
        if memory:
            parts.append(memory)
        
        # If nothing to report
        if len(parts) == 1:
            parts.append("Nothing specific to report. Have a great day! 🌟")
        
        return "\n\n".join(parts)
    
    async def _send_digest(self) -> None:
        """Send daily digest to all recipients."""
        if not self._chat_ids:
            logger.info("No digest recipients configured")
            return
        
        try:
            digest = await self._build_digest()
            
            for chat_id in self._chat_ids:
                try:
                    await self.send_callback(chat_id, digest)
                except Exception as e:
                    logger.error(f"Failed to send digest to {chat_id}: {e}")
            
            logger.info(f"Daily digest sent to {len(self._chat_ids)} recipient(s)")
            
        except Exception as e:
            logger.error(f"Digest generation error: {e}", exc_info=True)
    
    async def send_now(self, chat_id: int) -> str:
        """Generate and return digest immediately (for manual trigger)."""
        return await self._build_digest()
