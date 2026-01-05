from typing import Dict, List, Optional
from datetime import datetime, timedelta
from .storage import BenchmarkScore, MembershipDecision


class MembershipEngine:
    """
    Evaluates node membership based on benchmark scores.
    
    Rules:
    1. Node must have submitted a benchmark within MAX_BENCHMARK_AGE seconds
    2. Node's overall score must be >= THRESHOLD
    3. Membership is re-evaluated every epoch rotation
    """
    
    def __init__(self, threshold: float = 0.70, max_age_sec: int = 120):
        self.threshold = threshold
        self.max_age_sec = max_age_sec
    
    def evaluate(self, benchmarks: Dict[str, BenchmarkScore], node_ids: List[str]) -> Dict[str, MembershipDecision]:
        """
        Evaluate membership for all nodes.
        
        Returns:
            Dict[node_id] -> MembershipDecision
        """
        decisions = {}
        now = datetime.utcnow()
        
        for node_id in node_ids:
            benchmark = benchmarks.get(node_id)
            
            if not benchmark:
                # No benchmark submitted
                decisions[node_id] = MembershipDecision(
                    node_id=node_id,
                    membership="DENIED",
                    reason="no benchmark submitted"
                )
                continue
            
            # Parse timestamp
            try:
                ts = datetime.fromisoformat(benchmark.timestamp.replace('Z', '+00:00'))
                age_sec = (now - ts).total_seconds()
            except Exception:
                age_sec = float('inf')
            
            # Check freshness
            if age_sec > self.max_age_sec:
                decisions[node_id] = MembershipDecision(
                    node_id=node_id,
                    membership="DENIED",
                    reason=f"benchmark too old ({age_sec:.0f}s > {self.max_age_sec}s)",
                    last_benchmark_age_sec=age_sec
                )
                continue
            
            # Check score
            overall_score = benchmark.scores.get("overall", 0.0)
            if overall_score < self.threshold:
                decisions[node_id] = MembershipDecision(
                    node_id=node_id,
                    membership="DENIED",
                    reason=f"score {overall_score:.2f} < threshold {self.threshold:.2f}",
                    last_benchmark_age_sec=age_sec
                )
                continue
            
            # Allowed
            decisions[node_id] = MembershipDecision(
                node_id=node_id,
                membership="ALLOWED",
                reason=f"score {overall_score:.2f} >= {self.threshold:.2f}, fresh",
                last_benchmark_age_sec=age_sec
            )
        
        return decisions
