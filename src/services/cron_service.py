import asyncio
import logging
from datetime import datetime
from typing import Callable, List, Dict, Any

logger = logging.getLogger(__name__)

class CronJob:
    def __init__(self, name: str, interval_seconds: int, callback: Callable, args: tuple = (), kwargs: dict = {}):
        self.name = name
        self.interval = interval_seconds
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        self.last_run = None
        self.task = None

    async def run(self):
        while True:
            try:
                # logger.info(f"⏰ Cron Job Executing: {self.name}")
                self.last_run = datetime.now()
                if asyncio.iscoroutinefunction(self.callback):
                    await self.callback(*self.args, **self.kwargs)
                else:
                    self.callback(*self.args, **self.kwargs)
            except Exception as e:
                logger.error(f"❌ Cron Job Error ({self.name}): {e}")
            
            await asyncio.sleep(self.interval)

class CronService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CronService, cls).__new__(cls)
            cls._instance.jobs: Dict[str, CronJob] = {}
        return cls._instance

    def add_job(self, name: str, interval_seconds: int, callback: Callable, *args, **kwargs):
        if name in self.jobs:
            logger.warning(f"Cron job {name} already exists. Overwriting.")
            self.stop_job(name)
        
        job = CronJob(name, interval_seconds, callback, args, kwargs)
        self.jobs[name] = job
        job.task = asyncio.create_task(job.run())
        logger.info(f"📅 Scheduled Cron Job: {name} (every {interval_seconds}s)")

    def stop_job(self, name: str):
        if name in self.jobs:
            self.jobs[name].task.cancel()
            del self.jobs[name]
            logger.info(f"🛑 Stopped Cron Job: {name}")

    def list_jobs(self):
        return [
            {
                "name": name,
                "interval": job.interval,
                "last_run": job.last_run.isoformat() if job.last_run else "Never"
            }
            for name, job in self.jobs.items()
        ]

cron_service = CronService()
