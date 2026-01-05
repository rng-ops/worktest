import pytest
from app.membership import MembershipEngine
from app.storage import BenchmarkScore
from datetime import datetime, timedelta


def test_membership_allowed():
    """Test node is allowed when score >= threshold and fresh."""
    engine = MembershipEngine(threshold=0.70, max_age_sec=120)
    
    benchmarks = {
        "node-a": BenchmarkScore(
            node_id="node-a",
            timestamp=datetime.utcnow().isoformat() + "Z",
            suite_version="poc-0.1",
            scores={"overall": 0.90}
        )
    }
    
    decisions = engine.evaluate(benchmarks, ["node-a"])
    
    assert decisions["node-a"].membership == "ALLOWED"


def test_membership_score_too_low():
    """Test node is denied when score < threshold."""
    engine = MembershipEngine(threshold=0.70, max_age_sec=120)
    
    benchmarks = {
        "node-c": BenchmarkScore(
            node_id="node-c",
            timestamp=datetime.utcnow().isoformat() + "Z",
            suite_version="poc-0.1",
            scores={"overall": 0.40}
        )
    }
    
    decisions = engine.evaluate(benchmarks, ["node-c"])
    
    assert decisions["node-c"].membership == "DENIED"
    assert "score" in decisions["node-c"].reason.lower()


def test_membership_too_old():
    """Test node is denied when benchmark is too old."""
    engine = MembershipEngine(threshold=0.70, max_age_sec=120)
    
    old_timestamp = (datetime.utcnow() - timedelta(seconds=150)).isoformat() + "Z"
    benchmarks = {
        "node-b": BenchmarkScore(
            node_id="node-b",
            timestamp=old_timestamp,
            suite_version="poc-0.1",
            scores={"overall": 0.90}
        )
    }
    
    decisions = engine.evaluate(benchmarks, ["node-b"])
    
    assert decisions["node-b"].membership == "DENIED"
    assert "old" in decisions["node-b"].reason.lower()


def test_membership_no_benchmark():
    """Test node is denied when no benchmark submitted."""
    engine = MembershipEngine(threshold=0.70, max_age_sec=120)
    
    benchmarks = {}
    
    decisions = engine.evaluate(benchmarks, ["node-unknown"])
    
    assert decisions["node-unknown"].membership == "DENIED"
    assert "benchmark" in decisions["node-unknown"].reason.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
