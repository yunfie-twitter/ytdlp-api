"""Supervisor for worker processes with health monitoring and recovery"""
import logging
import asyncio
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WorkerHealth:
    """Health status of a worker"""
    worker_id: str
    is_alive: bool
    last_heartbeat: Optional[datetime]
    error_count: int
    processed_count: int
    uptime_seconds: float
    memory_mb: float


class WorkerSupervisor:
    """Supervises worker processes with automatic recovery"""
    
    def __init__(self, heartbeat_timeout_seconds: int = 30):
        self.workers: Dict[str, dict] = {}
        self.heartbeat_timeout = timedelta(seconds=heartbeat_timeout_seconds)
        self.worker_stats: Dict[str, Dict] = {}
        self.restart_count: Dict[str, int] = {}
    
    def register_worker(
        self,
        worker_id: str,
        process_func,
        process_kwargs: dict = None
    ):
        """Register a new worker
        
        Args:
            worker_id: Unique worker identifier
            process_func: Async function to run
            process_kwargs: Kwargs for process_func
        """
        self.workers[worker_id] = {
            "id": worker_id,
            "process_func": process_func,
            "kwargs": process_kwargs or {},
            "task": None,
            "created_at": datetime.utcnow(),
            "last_heartbeat": None
        }
        self.worker_stats[worker_id] = {
            "processed": 0,
            "errors": 0,
            "restarts": 0
        }
        logger.info(f"Worker {worker_id} registered")
    
    async def start_worker(self, worker_id: str) -> bool:
        """Start a worker process
        
        Returns:
            bool: True if started successfully
        """
        if worker_id not in self.workers:
            logger.error(f"Worker {worker_id} not registered")
            return False
        
        worker = self.workers[worker_id]
        
        try:
            # Cancel existing task if running
            if worker["task"] and not worker["task"].done():
                worker["task"].cancel()
                await asyncio.sleep(0.1)
            
            # Create new task
            worker["task"] = asyncio.create_task(
                self._run_worker_with_recovery(worker_id)
            )
            
            logger.info(f"Worker {worker_id} started")
            return True
        
        except Exception as e:
            logger.error(f"Error starting worker {worker_id}: {e}")
            return False
    
    async def _run_worker_with_recovery(self, worker_id: str):
        """Run worker with automatic restart on failure"""
        max_consecutive_errors = 5
        error_count = 0
        
        while True:
            try:
                worker = self.workers[worker_id]
                process_func = worker["process_func"]
                
                # Run worker process
                logger.debug(f"Worker {worker_id} started processing")
                await process_func(**worker["kwargs"])
                
                # Reset error count on success
                error_count = 0
                
            except asyncio.CancelledError:
                logger.info(f"Worker {worker_id} cancelled")
                break
            
            except Exception as e:
                error_count += 1
                self.worker_stats[worker_id]["errors"] += 1
                
                logger.error(
                    f"Worker {worker_id} error ({error_count}/{max_consecutive_errors}): {e}",
                    exc_info=True
                )
                
                if error_count >= max_consecutive_errors:
                    logger.critical(
                        f"Worker {worker_id} exceeded max consecutive errors, stopping"
                    )
                    break
                
                # Wait before retry
                await asyncio.sleep(min(2 ** error_count, 30))
    
    async def stop_worker(self, worker_id: str, timeout: int = 10) -> bool:
        """Stop a worker gracefully
        
        Returns:
            bool: True if stopped
        """
        if worker_id not in self.workers:
            return False
        
        worker = self.workers[worker_id]
        
        try:
            if worker["task"] and not worker["task"].done():
                worker["task"].cancel()
                
                try:
                    await asyncio.wait_for(worker["task"], timeout=timeout)
                except asyncio.TimeoutError:
                    logger.warning(f"Worker {worker_id} failed to stop within {timeout}s")
                    return False
            
            logger.info(f"Worker {worker_id} stopped")
            return True
        
        except Exception as e:
            logger.error(f"Error stopping worker {worker_id}: {e}")
            return False
    
    async def restart_worker(self, worker_id: str) -> bool:
        """Restart a worker
        
        Returns:
            bool: True if restarted
        """
        logger.info(f"Restarting worker {worker_id}")
        
        # Stop existing
        await self.stop_worker(worker_id)
        
        # Update stats
        self.restart_count[worker_id] = self.restart_count.get(worker_id, 0) + 1
        
        # Start new
        await asyncio.sleep(1)  # Brief delay before restart
        return await self.start_worker(worker_id)
    
    def record_heartbeat(self, worker_id: str):
        """Record worker heartbeat"""
        if worker_id in self.workers:
            self.workers[worker_id]["last_heartbeat"] = datetime.utcnow()
    
    def record_processed_item(self, worker_id: str):
        """Record that worker processed an item"""
        if worker_id in self.worker_stats:
            self.worker_stats[worker_id]["processed"] += 1
    
    async def check_worker_health(self, worker_id: str) -> WorkerHealth:
        """Check health of a worker
        
        Returns:
            WorkerHealth object
        """
        if worker_id not in self.workers:
            return WorkerHealth(
                worker_id=worker_id,
                is_alive=False,
                last_heartbeat=None,
                error_count=0,
                processed_count=0,
                uptime_seconds=0,
                memory_mb=0
            )
        
        worker = self.workers[worker_id]
        stats = self.worker_stats.get(worker_id, {})
        
        is_alive = worker["task"] and not worker["task"].done()
        
        # Check for timeout
        if is_alive and worker["last_heartbeat"]:
            time_since_heartbeat = datetime.utcnow() - worker["last_heartbeat"]
            if time_since_heartbeat > self.heartbeat_timeout:
                logger.warning(
                    f"Worker {worker_id} timeout: no heartbeat for "
                    f"{time_since_heartbeat.total_seconds():.0f}s"
                )
                is_alive = False
        
        uptime = (datetime.utcnow() - worker["created_at"]).total_seconds()
        
        return WorkerHealth(
            worker_id=worker_id,
            is_alive=is_alive,
            last_heartbeat=worker["last_heartbeat"],
            error_count=stats.get("errors", 0),
            processed_count=stats.get("processed", 0),
            uptime_seconds=uptime,
            memory_mb=0  # Would require psutil integration
        )
    
    async def get_all_worker_health(self) -> List[WorkerHealth]:
        """Get health of all workers
        
        Returns:
            List of WorkerHealth objects
        """
        return [
            await self.check_worker_health(worker_id)
            for worker_id in self.workers.keys()
        ]


# Global instance
worker_supervisor = WorkerSupervisor()
