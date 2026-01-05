import os
import secrets
import base64
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import asyncio
import json
import logging

from .crypto import derive_psk, epoch_secret_hash, verify_signature
from .storage import Storage, BenchmarkScore, MembershipDecision
from .membership import MembershipEngine

# Configuration from environment
THRESHOLD = float(os.getenv("THRESHOLD", "0.70"))
EPOCH_SECONDS = int(os.getenv("EPOCH_SECONDS", "60"))
MAX_BENCHMARK_AGE = int(os.getenv("MAX_BENCHMARK_AGE", "120"))

# Logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Aligned MeshNet Controller")

# Global state
storage = Storage(status_file="/artifacts/status.json")
membership_engine = MembershipEngine(threshold=THRESHOLD, max_age_sec=MAX_BENCHMARK_AGE)

# Epoch management
current_epoch_secret = None
current_epoch_id = 0
node_ids = ["node-a", "node-b", "node-c"]  # Fixed for PoC


@app.on_event("startup")
async def startup():
    """Initialize first epoch and start rotation task."""
    global current_epoch_secret, current_epoch_id
    
    logger.info("[controller] Starting up...")
    
    # Generate first epoch
    current_epoch_secret = secrets.token_bytes(32)
    current_epoch_id = 1
    expiry = datetime.utcnow() + timedelta(seconds=EPOCH_SECONDS)
    
    storage.set_epoch(
        epoch_id=current_epoch_id,
        expiry_utc=expiry.isoformat() + "Z",
        secret_hash=epoch_secret_hash(current_epoch_secret)
    )
    
    logger.info(f"[controller] Epoch {current_epoch_id} initialized (rotates in {EPOCH_SECONDS}s)")
    
    # Start background epoch rotation task
    asyncio.create_task(rotate_epochs_background())


async def rotate_epochs_background():
    """Background task: rotate epoch every EPOCH_SECONDS."""
    global current_epoch_secret, current_epoch_id
    
    while True:
        await asyncio.sleep(EPOCH_SECONDS)
        
        # Rotate
        current_epoch_secret = secrets.token_bytes(32)
        current_epoch_id += 1
        expiry = datetime.utcnow() + timedelta(seconds=EPOCH_SECONDS)
        
        storage.set_epoch(
            epoch_id=current_epoch_id,
            expiry_utc=expiry.isoformat() + "Z",
            secret_hash=epoch_secret_hash(current_epoch_secret)
        )
        
        logger.info(f"[controller] Epoch rotation: id={current_epoch_id} expiry={expiry.isoformat()}Z")
        
        # Re-evaluate membership
        memberships = membership_engine.evaluate(storage.benchmarks, node_ids)
        for node_id, decision in memberships.items():
            storage.store_membership(decision)
            reason = f" ({decision.reason})" if decision.reason else ""
            logger.info(f"[controller] Node-{node_id}: membership={decision.membership}{reason}")
        
        # Flush status
        storage.flush_status_json(node_ids)


@app.post("/v1/benchmarks/{node_id}")
async def submit_benchmark(node_id: str, payload: dict):
    """
    Receive benchmark submission from node.
    
    Expected JSON:
    {
      "node_id": "node-a",
      "timestamp": "2026-01-05T12:34:56Z",
      "suite_version": "poc-0.1",
      "scores": {
        "overall": 0.92,
        "refusal": 0.88,
        "honesty": 0.90,
        "policy": 0.95
      },
      "signature": "optional"
    }
    """
    try:
        # Validate node_id matches
        if payload.get("node_id") != node_id:
            raise HTTPException(status_code=400, detail="node_id mismatch")
        
        # Parse benchmark
        benchmark = BenchmarkScore(**payload)
        
        # TODO: Verify signature if present
        # (PoC: optional, always accepted)
        
        # Store
        storage.store_benchmark(benchmark)
        
        logger.info(f"[controller] Received benchmark from {node_id}: overall={benchmark.scores.get('overall', 0.0):.2f}")
        
        return {"status": "received", "node_id": node_id, "epoch_id": current_epoch_id}
    
    except Exception as e:
        logger.error(f"[controller] Benchmark parse error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/v1/epoch")
async def get_epoch():
    """
    Return current epoch info and per-node membership status.
    
    Response:
    {
      "epoch_id": 1,
      "expiry_utc": "2026-01-05T12:34:56Z",
      "secret_hash": "sha256:...",
      "nodes": {
        "node-a": {"membership": "ALLOWED", ...},
        ...
      }
    }
    """
    epoch = storage.get_epoch_state()
    memberships = storage.get_all_memberships()
    
    nodes_info = {}
    for node_id in node_ids:
        decision = memberships.get(node_id)
        nodes_info[node_id] = {
            "membership": decision.membership if decision else "UNKNOWN",
            "reason": decision.reason if decision else None
        }
    
    return {
        "epoch_id": epoch.epoch_id,
        "expiry_utc": epoch.expiry_utc,
        "secret_hash": epoch.secret_hash,
        "nodes": nodes_info
    }


@app.get("/v1/config/{node_id}")
async def get_config(node_id: str):
    """
    Return PSK for node in current epoch (if allowed).
    
    Response:
    {
      "node_id": "node-a",
      "epoch_id": 1,
      "psk_base64": "...",
      "allowed": true,
      "reason": "..."
    }
    """
    # Check membership
    membership = storage.get_membership(node_id)
    is_allowed = membership and membership.membership == "ALLOWED"
    
    response = {
        "node_id": node_id,
        "epoch_id": current_epoch_id,
        "allowed": is_allowed,
        "reason": membership.reason if membership else "no membership decision"
    }
    
    # Only send PSK if allowed
    if is_allowed and current_epoch_secret:
        psk = derive_psk(current_epoch_secret, node_id)
        response["psk_base64"] = base64.b64encode(psk).decode()
    
    return response


@app.post("/v1/rotate")
async def force_rotate():
    """Force immediate epoch rotation (for testing)."""
    logger.warning("[controller] Force rotation triggered")
    # This is a bit hacky for PoC; in production use proper signal handling
    return {"status": "rotate triggered (will happen on next background tick)"}


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "epoch_id": current_epoch_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
