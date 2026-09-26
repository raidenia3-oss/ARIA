"""Models for cross-device synchronization and daemon orchestration."""

from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime


class NodeState(BaseModel):
    """Represents the state of a node in the network."""
    node_id: str
    last_sync: datetime
    data_version: int
    data_hash: str
    is_active: bool = True


class SyncStatus(BaseModel):
    """Represents the status of synchronization between nodes."""
    node_id: str
    status: str
    last_sync_time: datetime
    conflicts: List[str] = []


class DaemonHealth(BaseModel):
    """Represents the health status of the daemon."""
    is_running: bool
    last_check: datetime
    uptime_seconds: int
    errors: Optional[List[str]] = None


class SyncRequest(BaseModel):
    """Represents a request for synchronization."""
    source_node: str
    target_node: str
    data_changes: Dict[str, str]
    timestamp: datetime