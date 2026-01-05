#!/usr/bin/env python3
"""
Benchmark Emitter: Periodically generate and submit benchmark scores to the controller.

Each node emits JSON benchmarks with scores around a configurable mean.
Timestamps are RFC3339, and signature field is optional (PoC).
"""

import os
import sys
import json
import time
import random
import hashlib
from datetime import datetime
import requests


NODE_ID = os.getenv("NODE_ID", "node-a")
CONTROLLER_HOST = os.getenv("CONTROLLER_HOST", "http://controller:8000")
SCORE_MEAN = float(os.getenv("SCORE_MEAN", "0.70"))
EMIT_INTERVAL_SEC = int(os.getenv("EMIT_INTERVAL_SEC", "10"))

# Seed RNG by node_id for reproducibility
random.seed(int(hashlib.md5(NODE_ID.encode()).hexdigest(), 16))


def generate_benchmark():
    """Generate a benchmark JSON."""
    # Scores with some variance
    overall = max(0.0, min(1.0, random.gauss(SCORE_MEAN, 0.08)))
    refusal = max(0.0, min(1.0, random.gauss(SCORE_MEAN - 0.02, 0.10)))
    honesty = max(0.0, min(1.0, random.gauss(SCORE_MEAN + 0.02, 0.10)))
    policy = max(0.0, min(1.0, random.gauss(SCORE_MEAN, 0.08)))
    
    return {
        "node_id": NODE_ID,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "suite_version": "poc-0.1",
        "scores": {
            "overall": round(overall, 3),
            "refusal": round(refusal, 3),
            "honesty": round(honesty, 3),
            "policy": round(policy, 3),
        },
        "notes": f"Mean={SCORE_MEAN:.2f}",
        "signature": None  # Optional for PoC
    }


def submit_benchmark(benchmark):
    """POST benchmark to controller."""
    try:
        url = f"{CONTROLLER_HOST}/v1/benchmarks/{NODE_ID}"
        response = requests.post(url, json=benchmark, timeout=5)
        
        if response.status_code == 200:
            print(f"[{NODE_ID}] SUBMITTED benchmark suite_version={benchmark['suite_version']} overall={benchmark['scores']['overall']:.2f}", flush=True)
            return True
        else:
            print(f"[{NODE_ID}] Failed to submit: {response.status_code} {response.text}", file=sys.stderr, flush=True)
            return False
    except Exception as e:
        print(f"[{NODE_ID}] Exception: {e}", file=sys.stderr, flush=True)
        return False


def main():
    """Run benchmark emitter loop."""
    print(f"[{NODE_ID}] Benchmark emitter starting (mean={SCORE_MEAN:.2f}, interval={EMIT_INTERVAL_SEC}s)", flush=True)
    print(f"[{NODE_ID}] Controller: {CONTROLLER_HOST}", flush=True)
    
    iteration = 0
    while True:
        try:
            iteration += 1
            benchmark = generate_benchmark()
            submit_benchmark(benchmark)
            time.sleep(EMIT_INTERVAL_SEC)
        except KeyboardInterrupt:
            print(f"\n[{NODE_ID}] Shutting down", file=sys.stderr, flush=True)
            break
        except Exception as e:
            print(f"[{NODE_ID}] Error in main loop: {e}", file=sys.stderr, flush=True)
            time.sleep(EMIT_INTERVAL_SEC)


if __name__ == "__main__":
    main()
