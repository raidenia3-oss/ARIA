"""Daemon orchestration engine for AURA."""

import time
import threading
from datetime import datetime
from typing import Optional
from .models import DaemonHealth


class DaemonOrchestrator:
    """Handles the lifecycle and health of the daemon."""
    
    def __init__(self):
        self.health = DaemonHealth(
            is_running=True,
            last_check=datetime.now(),
            uptime_seconds=0,
            errors=None
        )
        self.running = True
        self.thread: Optional[threading.Thread] = None
        # Marca de arranque real: antes uptime_seconds guardaba time.time() (un
        # timestamp epoch, no un uptime) y /api/system/health lo exponía mal.
        self._started_at = time.time()
    
    def start(self) -> None:
        """Start the daemon orchestration thread."""
        self.running = True
        self.health.last_check = datetime.now()
        self.thread = threading.Thread(target=self._monitor_daemon, daemon=True)
        self.thread.start()
    
    def _monitor_daemon(self) -> None:
        """Monitor the daemon's health and restart if necessary."""
        while self.running:
            self.health.last_check = datetime.now()
            self.health.uptime_seconds = int(time.time() - self._started_at)
            
            if not self.health.is_running:
                print("Daemon is not running. Attempting to restart...")
                self._restart_daemon()
            
            time.sleep(5)
    
    def _restart_daemon(self) -> None:
        """Simulate restarting the daemon."""
        print("Restarting daemon...")
        self.health.is_running = True
        self.health.errors = None
    
    def stop(self) -> None:
        """Stop the daemon orchestration thread."""
        self.running = False
        if self.thread:
            self.thread.join()