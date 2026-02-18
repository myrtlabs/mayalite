"""
Scheduler for MayaLite v0.4.

Handles:
- Heartbeat polling at configurable intervals
- Memory compaction scheduling
- Reminder scheduling (v0.4)
- Daily digest scheduling (v0.4)
"""

import logging
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class MayaScheduler:
    """
    APScheduler-based scheduler for MayaLite.
    
    Handles periodic heartbeats, scheduled compaction,
    reminders, and daily digest.
    """
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._heartbeat_callback: Optional[Callable] = None
        self._compact_callback: Optional[Callable] = None
        self._started = False
    
    def get_scheduler(self) -> AsyncIOScheduler:
        """Get the underlying APScheduler instance."""
        return self.scheduler
    
    def setup_heartbeat(
        self,
        callback: Callable,
        interval_minutes: int = 30,
    ) -> None:
        """Configure heartbeat job."""
        self._heartbeat_callback = callback
        
        self.scheduler.add_job(
            callback,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="heartbeat",
            name="Heartbeat",
            replace_existing=True,
            max_instances=1,
        )
        
        logger.info(f"Heartbeat scheduled every {interval_minutes} minutes")
    
    def setup_compaction(
        self,
        callback: Callable,
        cron_expression: str = "0 3 * * *",
    ) -> None:
        """Configure memory compaction job."""
        self._compact_callback = callback
        
        parts = cron_expression.split()
        if len(parts) != 5:
            logger.warning(f"Invalid cron expression: {cron_expression}, using default")
            parts = ["0", "3", "*", "*", "*"]
        
        self.scheduler.add_job(
            callback,
            trigger=CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            ),
            id="compaction",
            name="Memory Compaction",
            replace_existing=True,
            max_instances=1,
        )
        
        logger.info(f"Memory compaction scheduled: {cron_expression}")
    
    def start(self) -> None:
        """Start the scheduler."""
        if not self._started:
            self.scheduler.start()
            self._started = True
            logger.info("Scheduler started")
    
    def stop(self) -> None:
        """Stop the scheduler."""
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False
            logger.info("Scheduler stopped")
    
    def trigger_heartbeat_now(self) -> bool:
        """Manually trigger a heartbeat immediately."""
        if self._heartbeat_callback:
            job = self.scheduler.get_job("heartbeat")
            if job:
                job.modify(next_run_time=None)
                return True
        return False
    
    def get_next_heartbeat(self) -> Optional[str]:
        """Get the next scheduled heartbeat time as ISO string."""
        job = self.scheduler.get_job("heartbeat")
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
        return None
    
    def get_next_compaction(self) -> Optional[str]:
        """Get the next scheduled compaction time as ISO string."""
        job = self.scheduler.get_job("compaction")
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
        return None
    
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._started and self.scheduler.running
    
    def list_jobs(self) -> list:
        """List all scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            })
        return jobs
