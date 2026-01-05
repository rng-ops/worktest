# Integration Guide

This document explains how to integrate aligned-meshnet-poc with real benchmark harnesses and infrastructure.

## Overview

The PoC demonstrates the **control plane** and **enforcement mechanism** for mesh segmentation. Production deployments will plug in:

1. **Real benchmark harnesses** (InfraSim, HackAssist, custom)
2. **Policy engines** (custom rules, committees)
3. **Infrastructure** (cloud providers, Kubernetes, enterprise networks)

This guide maps integration points to code locations.

---

## Benchmark Harness Integration

### Current (PoC)

**File:** [`node/scripts/benchmark_emitter.py`](../node/scripts/benchmark_emitter.py)

Generates mock scores:
```python
overall = random.gauss(SCORE_MEAN, 0.08)
refusal = random.gauss(SCORE_MEAN - 0.02, 0.10)
...
```

### Integration Point

Replace the score generation with real benchmark harness output:

```python
# Before (PoC)
overall = random.gauss(SCORE_MEAN, 0.08)

# After (Production)
from infrasim import run_benchmark_suite

result = run_benchmark_suite(
    model_path="/path/to/model",
    test_suite="alignment_v1",
    num_samples=100
)

overall = result.aggregate_score  # e.g., 0.92
refusal = result.refusal_score
honesty = result.honesty_score
policy = result.policy_compliance
```

### InfraSim Integration Example

InfraSim is a sandbox environment for reproducible AI benchmarking. Integration:

```python
# In benchmark_emitter.py

import infrasim
from infrasim.benchmarks import AlignmentSuite

def generate_benchmark_with_infrasim():
    """Run InfraSim suite and extract scores."""
    
    # Configure appliance
    config = {
        "model": "llama-7b-chat",
        "seed": hash(NODE_ID),  # Deterministic per node
        "device": "cpu"  # or "cuda" if available
    }
    
    # Run suite
    suite = AlignmentSuite(config)
    results = suite.run(
        num_samples=10,
        timeout_sec=60
    )
    
    # Extract scores
    benchmark = {
        "node_id": NODE_ID,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "suite_version": "infrasim-v2.1",
        "scores": {
            "overall": results.overall_score,
            "refusal": results.refusal_rate,
            "honesty": results.truthfulness_score,
            "policy": results.policy_compliance,
            "harmful_refusal_accuracy": results.harmful_refusal_accuracy,
            "benign_assistance_rate": results.benign_assistance_rate,
        },
        "notes": f"model={config['model']}, samples={results.num_completed}"
    }
    
    return benchmark
```

### HackAssist Integration Example

HackAssist evaluates adversarial robustness. Integration:

```python
from hackassist import AdversarialBenchmark, attack_suite

def generate_benchmark_with_hackassist():
    """Run HackAssist suite and extract scores."""
    
    benchmark_suite = AdversarialBenchmark(
        model_endpoint=f"http://localhost:5000/inference",
        num_attack_scenarios=50
    )
    
    results = benchmark_suite.run()
    
    benchmark = {
        "node_id": NODE_ID,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "suite_version": "hackassist-v1.0",
        "scores": {
            "overall": results.robustness_score,  # Average survival rate under attack
            "injection_defense": results.injection_attack_success_rate,
            "prompt_injection": results.prompt_injection_defense,
            "token_smuggling": results.token_smuggling_defense,
            "adversarial_examples": results.adversarial_robustness,
        },
        "notes": f"attack_scenarios={results.num_attacked}"
    }
    
    return benchmark
```

### Custom Harness Template

```python
def generate_benchmark_with_custom_harness():
    """Template for custom benchmark harness."""
    
    from my_org.benchmarks import evaluate_alignment
    
    # Run evaluation
    result = evaluate_alignment(
        node_id=NODE_ID,
        test_suite="custom-v1",
        num_samples=20
    )
    
    # Map to standard schema
    benchmark = {
        "node_id": NODE_ID,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "suite_version": "custom-v1",
        "scores": {
            "overall": result.aggregate(),  # Custom aggregation function
            "metric_1": result.dimension_1,
            "metric_2": result.dimension_2,
            # ... other scores
        },
        "notes": f"custom metadata"
    }
    
    return benchmark
```

---

## Membership Policy Integration

### Current (PoC)

**File:** [`controller/app/membership.py`](../controller/app/membership.py)

Simple threshold rule:
```python
if overall_score >= THRESHOLD and freshness_ok:
    membership = ALLOWED
else:
    membership = DENIED
```

### Integration Point 1: Threshold by Policy Class

In production, different nodes/models may have different thresholds:

```python
# In membership.py

POLICY_THRESHOLDS = {
    "training": 0.75,      # Stricter for training nodes
    "inference": 0.70,     # Standard for inference
    "experimental": 0.60,  # Relaxed for new models
}

def evaluate(self, benchmarks, node_ids):
    decisions = {}
    for node_id in node_ids:
        policy_class = get_node_policy(node_id)  # e.g., "training"
        threshold = POLICY_THRESHOLDS.get(policy_class, self.threshold)
        
        benchmark = benchmarks.get(node_id)
        if benchmark and benchmark.scores.get("overall", 0) >= threshold:
            decisions[node_id] = MembershipDecision(
                node_id=node_id,
                membership="ALLOWED",
                reason=f"score {benchmark.scores['overall']:.2f} >= {threshold:.2f} ({policy_class})"
            )
        else:
            decisions[node_id] = MembershipDecision(
                node_id=node_id,
                membership="DENIED",
                reason=f"score below {threshold:.2f} threshold ({policy_class})"
            )
    
    return decisions
```

### Integration Point 2: Committee Voting

Replace single-controller decisions with quorum:

```python
from typing import List

class CommitteeVote:
    """Multi-controller consensus on membership."""
    
    def __init__(self, num_controllers: int = 3, quorum: int = 2):
        self.num_controllers = num_controllers
        self.quorum = quorum
    
    def evaluate(self, benchmarks, node_ids):
        """Collect votes from all controllers."""
        decisions = {}
        
        for node_id in node_ids:
            votes = []  # [ALLOWED, ALLOWED, DENIED] from three controllers
            
            # Fetch vote from each controller via RPC or message queue
            for controller_id in range(self.num_controllers):
                vote = self.vote_from_controller(controller_id, node_id, benchmarks)
                votes.append(vote)
            
            # Tally votes
            allowed_votes = sum(1 for v in votes if v == "ALLOWED")
            membership = "ALLOWED" if allowed_votes >= self.quorum else "DENIED"
            
            decisions[node_id] = MembershipDecision(
                node_id=node_id,
                membership=membership,
                reason=f"committee vote: {allowed_votes}/{self.num_controllers} ALLOWED"
            )
        
        return decisions
    
    def vote_from_controller(self, controller_id: int, node_id: str, benchmarks):
        # Placeholder: call remote controller endpoint
        pass
```

### Integration Point 3: Time-Series Analysis

Replace single-benchmark check with trend analysis:

```python
class TrendAnalysisMembership(MembershipEngine):
    """Detect behavioral drift using EWMA (Exponential Weighted Moving Average)."""
    
    def __init__(self, threshold: float = 0.70, alpha: float = 0.3):
        super().__init__(threshold)
        self.alpha = alpha
        self.history = {}  # node_id -> [score1, score2, ...]
    
    def evaluate(self, benchmarks, node_ids):
        decisions = {}
        
        for node_id in node_ids:
            benchmark = benchmarks.get(node_id)
            if not benchmark:
                decisions[node_id] = MembershipDecision(
                    node_id=node_id,
                    membership="DENIED",
                    reason="no benchmark"
                )
                continue
            
            # Track score history
            score = benchmark.scores.get("overall", 0)
            if node_id not in self.history:
                self.history[node_id] = []
            self.history[node_id].append(score)
            
            # Compute EWMA trend
            if len(self.history[node_id]) >= 3:
                ewma = self._compute_ewma(self.history[node_id])
                trend = ewma - score  # Positive trend = improving
                
                # Membership based on both current score and trend
                if score >= self.threshold and trend >= -0.1:  # Allow small decline
                    membership = "ALLOWED"
                    reason = f"score {score:.2f}, EWMA {ewma:.2f}, trend {trend:+.2f}"
                else:
                    membership = "DENIED"
                    reason = f"score declining: {score:.2f} → EWMA {ewma:.2f}, trend {trend:+.2f}"
            else:
                # Not enough history; use simple threshold
                membership = "ALLOWED" if score >= self.threshold else "DENIED"
                reason = f"building history ({len(self.history[node_id])}/3)"
            
            decisions[node_id] = MembershipDecision(
                node_id=node_id,
                membership=membership,
                reason=reason
            )
        
        return decisions
    
    def _compute_ewma(self, scores: List[float]) -> float:
        """Exponential Weighted Moving Average."""
        ewma = scores[0]
        for score in scores[1:]:
            ewma = self.alpha * score + (1 - self.alpha) * ewma
        return ewma
```

---

## WireGuard Configuration Integration

### Current (PoC)

**File:** [`terraform/main.tf`](../terraform/main.tf)

Generates static templates:
```hcl
content = <<-EOT
[Interface]
Address = 10.10.0.2/32
PrivateKey = (set by controller)
...
EOT
```

### Integration Point: Dynamic Peer Discovery

In production, nodes discover peers dynamically:

```python
# In controller/app/main.py, add endpoint for peer discovery

@app.get("/v1/peers/{node_id}")
async def discover_peers(node_id: str):
    """
    Return list of allowed peers for this node.
    
    Nodes use this to dynamically configure WireGuard without hardcoding peers.
    """
    membership = storage.get_all_memberships()
    allowed_peers = [
        peer_id for peer_id in membership
        if membership[peer_id].membership == "ALLOWED"
    ]
    
    # Map peer_id to tunnel IP (from known configuration)
    peers = []
    for peer_id in allowed_peers:
        if peer_id != node_id:  # Exclude self
            peer_info = {
                "node_id": peer_id,
                "tunnel_ip": TUNNEL_IPS.get(peer_id),  # e.g., "10.10.0.3"
                "public_key": get_peer_public_key(peer_id)  # WireGuard pubkey
            }
            peers.append(peer_info)
    
    return {
        "node_id": node_id,
        "peers": peers,
        "allowed_subnet": "10.10.0.0/24"
    }
```

Then, node config agent dynamically rewrites `/etc/wireguard/wg0.conf`:

```python
# In node/scripts/config_agent.py

def fetch_and_apply_peer_config():
    """Fetch peer list and update WireGuard config."""
    
    response = requests.get(f"{CONTROLLER_HOST}/v1/peers/{NODE_ID}")
    peers_info = response.json()["peers"]
    
    # Generate WireGuard config
    config = f"""
[Interface]
Address = 10.10.0.{NODE_ID_NUM}/32
PrivateKey = {read_privkey()}
ListenPort = 51820
"""
    
    for peer in peers_info:
        pubkey = peer["public_key"]
        allowed_ip = peer["tunnel_ip"] + "/32"
        config += f"""
[Peer]
PublicKey = {pubkey}
AllowedIPs = {allowed_ip}
PreSharedKey = {psk}
"""
    
    # Apply config
    subprocess.run(["wg-quick", "down", "wg0"], capture_output=True)
    with open("/etc/wireguard/wg0.conf", "w") as f:
        f.write(config)
    subprocess.run(["wg-quick", "up", "wg0"])
```

---

## Routing & Policy Integration

### Multi-Segment Routing

Different policy classes may have separate tunnels:

```python
# In controller/app/main.py

@app.get("/v1/subnets/{node_id}")
async def get_node_subnets(node_id: str):
    """
    Return which subnets (policy classes) node is allowed to access.
    
    Example: training node has access to ["training", "shared"]
             inference node has access to ["inference", "shared"]
    """
    policy_class = get_node_policy(node_id)
    membership = storage.get_membership(node_id)
    
    if membership and membership.membership == "ALLOWED":
        allowed_subnets = get_allowed_subnets(policy_class)
        return {
            "node_id": node_id,
            "policy_class": policy_class,
            "allowed_subnets": allowed_subnets  # e.g., ["training", "shared"]
        }
    else:
        return {"node_id": node_id, "allowed_subnets": []}
```

Nodes then maintain separate WireGuard interfaces (wg0, wg1, wg2) per subnet.

---

## Attestation Integration

### Hardware Attestation (Future)

Integrate with Intel SGX or ARM TrustZone:

```python
# In controller/app/crypto.py

from intel_sgx_sdk import verify_quote

def verify_node_attestation(node_id: str, attestation_quote: str) -> bool:
    """
    Verify that node is running in a trusted enclave.
    
    Attestation proves:
    - Hardware is genuine (Intel/ARM)
    - Firmware is current
    - Code/data hashes match known good values
    """
    try:
        verified_quote = verify_quote(attestation_quote)
        # Check enclave mrenclave (code hash) against whitelist
        if verified_quote.mrenclave in TRUSTED_ENCLAVES:
            return True
    except Exception as e:
        logging.error(f"Attestation failed for {node_id}: {e}")
    
    return False
```

### Software Attestation (Immediate)

Verify node code via code hash:

```python
# In benchmark submission, add code_hash

benchmark = {
    "node_id": "node-a",
    "timestamp": "...",
    "scores": {...},
    "code_hash": "sha256:abc123...",  # SHA256 of node image
    "signature": "..."
}

# In controller, verify
def verify_node_code_hash(node_id: str, code_hash: str) -> bool:
    """Check that node is running approved code."""
    expected_hash = APPROVED_NODE_HASHES.get(node_id)
    return code_hash == expected_hash
```

---

## Kubernetes Integration

For Kubernetes-based deployments:

```yaml
# Example: Kubernetes CRD for Aligned Mesh Node

apiVersion: alignedmesh.io/v1alpha1
kind: MeshNode
metadata:
  name: node-a
  namespace: inference
spec:
  policyClass: inference
  benchmark:
    suite: infrasim
    interval: 10s
    timeout: 30s
  membershipThreshold: 0.70
  image: aligned-meshnet:latest
  resources:
    requests:
      memory: "2Gi"
      cpu: "1"
status:
  membership: ALLOWED
  lastBenchmarkScore: 0.91
  epoch: 2
```

Controller runs as a Kubernetes operator:

```python
# Kubernetes Operator Pattern

from kopf import on_event

@on_event('alignedmesh.io', 'meshnode', 'create')
def on_meshnode_created(spec, name, **kwargs):
    """Register node with controller."""
    node_id = f"{name}"
    store_node_config(node_id, spec)
    logger.info(f"MeshNode {node_id} created")

@on_event('alignedmesh.io', 'meshnode', 'delete')
def on_meshnode_deleted(spec, name, **kwargs):
    """Deregister node."""
    node_id = f"{name}"
    revoke_node(node_id)
    logger.info(f"MeshNode {node_id} deleted")
```

---

## Deployment Environments

### Development (Current)
- Docker Compose (single machine)
- Mock benchmarks
- See: `make demo`

### Staging
- Terraform → AWS/GCP/Azure
- Real benchmark harness (InfraSim)
- Controller replicated (3 nodes, Raft)
- TLS enabled
- See: `terraform/` (extensible)

### Production
- Kubernetes cluster
- Distributed controllers (Raft or BFT)
- Hardware attestation (Intel SGX)
- Immutable audit log
- Rate limiting + DDoS protection
- Observability (Prometheus, Jaeger)

---

## Monitoring & Observability Integration

### Prometheus Metrics (Future)

```python
# In controller/app/main.py

from prometheus_client import Counter, Gauge, Histogram

benchmark_submissions = Counter(
    'mesh_benchmark_submissions_total',
    'Total benchmark submissions',
    ['node_id', 'status']
)

membership_changes = Counter(
    'mesh_membership_changes_total',
    'Total membership changes',
    ['node_id', 'from_status', 'to_status']
)

node_score_gauge = Gauge(
    'mesh_node_score',
    'Current node score',
    ['node_id']
)

epoch_rotation_duration_seconds = Histogram(
    'mesh_epoch_rotation_duration_seconds',
    'Time to rotate epoch and re-evaluate membership'
)

@app.post("/metrics")
async def get_metrics():
    """Export Prometheus metrics."""
    from prometheus_client import generate_latest
    return generate_latest()
```

### Distributed Tracing (Jaeger)

```python
from jaeger_client import Config

config = Config(
    config={
        'sampler': {
            'type': 'const',
            'param': 1,
        },
        'logging': True,
    },
    service_name='aligned-meshnet-controller',
)
jaeger_tracer = config.initialize_tracer()

@app.post("/v1/benchmarks/{node_id}")
@jaeger_tracer.trace_function
async def submit_benchmark(node_id: str, payload: dict):
    # Traces will be sent to Jaeger agent
    ...
```

---

## Further Reading

- [InfraSim Documentation](https://example.com/infrasim)
- [HackAssist Research Paper](https://example.com/hackassist)
- [Kubernetes Operators](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)
- [WireGuard Configuration](https://www.wireguard.com/)
- [Raft Consensus](https://raft.github.io/)

---

## Questions?

Open an issue or contact the maintainers with integration questions.
