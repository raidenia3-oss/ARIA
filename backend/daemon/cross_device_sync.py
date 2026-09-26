"""Cross-device synchronization engine for AURA."""

import hashlib
import json
from typing import Dict, List
from datetime import datetime
from .models import NodeState, SyncStatus, SyncRequest


class CrossDeviceSync:
    """Handles synchronization between local nodes."""
    
    def __init__(self):
        self.nodes: Dict[str, NodeState] = {}
        self.sync_status: Dict[str, SyncStatus] = {}
        
    def register_node(self, node_id: str) -> None:
        """Register a new node in the network."""
        if node_id not in self.nodes:
            self.nodes[node_id] = NodeState(
                node_id=node_id,
                last_sync=datetime.now(),
                data_version=0,
                data_hash=""
            )
    
    def update_node_state(self, node_id: str, data_hash: str, data_version: int) -> None:
        """Update the state of a node."""
        if node_id in self.nodes:
            self.nodes[node_id].data_hash = data_hash
            self.nodes[node_id].data_version = data_version
            self.nodes[node_id].last_sync = datetime.now()
    
    def generate_data_hash(self, data: str) -> str:
        """Generate a hash for the data to be synchronized."""
        return hashlib.sha256(data.encode()).hexdigest()
    
    def create_sync_request(self, source_node: str, target_node: str, data_changes: Dict[str, str]) -> SyncRequest:
        """Create a synchronization request."""
        return SyncRequest(
            source_node=source_node,
            target_node=target_node,
            data_changes=data_changes,
            timestamp=datetime.now()
        )
    
    def process_sync_request(self, request: SyncRequest) -> SyncStatus:
        """Process a synchronization request."""
        if request.source_node not in self.nodes or request.target_node not in self.nodes:
            return SyncStatus(
                node_id=request.target_node,
                status="error",
                last_sync_time=datetime.now(),
                conflicts=["One or both nodes not found"]
            )
        
        # Simulate sync logic
        self.update_node_state(request.target_node, self.generate_data_hash(json.dumps(request.data_changes)), 1)
        return SyncStatus(
            node_id=request.target_node,
            status="success",
            last_sync_time=datetime.now()
        )