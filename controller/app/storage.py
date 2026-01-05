import json
import time
from typing import Dict, Optional, List
from pydantic import BaseModel
from datetime import datetime, timedelta


class BenchmarkScore(BaseModel):
    """Benchmark submission from a node."""
    node_id: str
    timestamp: str
    suite_version: str
    scores: Dict[str, float]
    notes: Optional[str] = None
    signature: Optional[str] = None


class MembershipDecision(BaseModel):
    """Membership status for a node."""
    node_id: str
    membership: str  # "ALLOWED" or "DENIED"
    reason: Optional[str] = None
    last_benchmark_age_sec: Optional[float] = None


class EpochState(BaseModel):
    """Current epoch state."""
    epoch_id: int
    expiry_utc: str
    secret_hash: str


class NodeStatus(BaseModel):
    """Per-node status."""
    membership: str
    last_benchmark: Optional[Dict] = None
    last_update_utc: str
    psk_valid: bool
    reason: Optional[str] = None


class Storage:
    """In-memory state management with JSON persistence."""
    
    def __init__(self, status_file: str = "/artifacts/status.json"):
        self.status_file = status_file
        self.benchmarks: Dict[str, BenchmarkScore] = {}
        self.memberships: Dict[str, MembershipDecision] = {}
        self.epoch_id = 0
        self.epoch_expiry_utc = ""
        self.epoch_secret_hash = ""
    
    def store_benchmark(self, score: BenchmarkScore) -> None:
        """Store latest benchmark for node."""
        self.benchmarks[score.node_id] = score
    
    def store_membership(self, decision: MembershipDecision) -> None:
        """Store membership decision."""
        self.memberships[decision.node_id] = decision
    
    def set_epoch(self, epoch_id: int, expiry_utc: str, secret_hash: str) -> None:
        """Update current epoch."""
        self.epoch_id = epoch_id
        self.epoch_expiry_utc = expiry_utc
        self.epoch_secret_hash = secret_hash
    
    def get_benchmark(self, node_id: str) -> Optional[BenchmarkScore]:
        """Retrieve latest benchmark for node."""
        return self.benchmarks.get(node_id)
    
    def get_membership(self, node_id: str) -> Optional[MembershipDecision]:
        """Retrieve membership decision for node."""
        return self.memberships.get(node_id)
    
    def get_all_memberships(self) -> Dict[str, MembershipDecision]:
        """Retrieve all membership decisions."""
        return self.memberships
    
    def get_epoch_state(self) -> EpochState:
        """Retrieve current epoch state."""
        return EpochState(
            epoch_id=self.epoch_id,
            expiry_utc=self.epoch_expiry_utc,
            secret_hash=self.epoch_secret_hash
        )
    
    def flush_status_json(self, node_ids: List[str]) -> None:
        """
        Write status.json for observability.
        """
        status = {
            "epoch": {
                "id": self.epoch_id,
                "expiry_utc": self.epoch_expiry_utc,
                "secret_hash": self.epoch_secret_hash
            },
            "nodes": {}
        }
        
        for node_id in node_ids:
            benchmark = self.get_benchmark(node_id)
            membership = self.get_membership(node_id)
            
            node_data = {
                "membership": membership.membership if membership else "UNKNOWN",
                "last_update_utc": datetime.utcnow().isoformat() + "Z"
            }
            
            if benchmark:
                node_data["last_benchmark"] = {
                    "overall": benchmark.scores.get("overall", 0.0),
                    "timestamp": benchmark.timestamp,
                    "suite_version": benchmark.suite_version
                }
            
            if membership and membership.reason:
                node_data["reason"] = membership.reason
            
            status["nodes"][node_id] = node_data
        
        try:
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            print(f"[!] Failed to write status.json: {e}")
