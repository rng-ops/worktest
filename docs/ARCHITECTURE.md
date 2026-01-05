# Architecture

## System Overview

The aligned-meshnet-poc demonstrates a control-plane driven mesh network segmentation system where behavioral benchmarks determine node membership.

```
┌──────────────────────────────────────┐
│    Mesh Controller (FastAPI)         │
│                                      │
│  • Epoch Manager                     │
│  • Membership Engine                 │
│  • PSK Derivation (HMAC-SHA256)      │
│  • Status Publisher                  │
└──────────────┬───────────────────────┘
               │
     ┌─────────┼─────────┐
     ↓         ↓         ↓
┌─────────┐ ┌─────────┐ ┌─────────┐
│ Node-A  │ │ Node-B  │ │ Node-C  │
│ WG+Mesh │ │ WG+Mesh │ │ WG+Mesh │
└────┬────┘ └────┬────┘ └────┬────┘
     │ Benchmarks │ Benchmarks │
     └─────┬──────┴────┬───────┘
           │ Config    │
           └───────────┘
```

## Components

### 1. Controller (`controller/`)

**Purpose:** Central authority for epoch management, membership evaluation, and PSK distribution.

**Responsibilities:**
- Receive benchmark submissions from nodes
- Evaluate membership based on threshold rules
- Derive per-node PSKs from epoch secret
- Serve config/PSK to allowed nodes only
- Manage epoch rotation (every EPOCH_SECONDS)
- Publish status.json for observability

**Key Files:**
- `app/main.py` – FastAPI HTTP server
- `app/membership.py` – Membership logic (threshold, freshness)
- `app/crypto.py` – HMAC-based PSK derivation
- `app/storage.py` – In-memory + JSON persistence

**HTTP Endpoints:**
- `POST /v1/benchmarks/{node_id}` – Submit benchmark score
- `GET /v1/epoch` – Query current epoch + membership status
- `GET /v1/config/{node_id}` – Request current PSK (if allowed)
- `POST /v1/rotate` – Force immediate epoch rotation (testing)
- `GET /health` – Health check

**State:**
- Current epoch ID, secret, expiry
- Latest benchmark per node
- Membership decision per node (in-memory + flushed to JSON)

### 2. Node Service (`node/`)

**Purpose:** Each node runs three sub-services that together maintain mesh connectivity and report behavioral status.

**Sub-services:**

#### 2a. Benchmark Emitter (`scripts/benchmark_emitter.py`)
- Generates JSON benchmarks with scores around a configurable mean
- Posts to controller every EMIT_INTERVAL_SEC (default 10s)
- Scores include: overall, refusal, honesty, policy
- Timestamps in RFC3339 format
- Optional signature field (PoC: unused)

#### 2b. Config Agent (`scripts/config_agent.py`)
- Polls controller for latest config every POLL_INTERVAL_SEC (default 10s)
- Parses membership decision (ALLOWED / DENIED)
- If ALLOWED: receives PSK and applies to WireGuard
- If DENIED: node loses tunnel connectivity (quarantine)
- Logs membership transitions

#### 2c. Network Probe (`scripts/net_probe.sh`)
- Periodically pings peer nodes every PROBE_INTERVAL_SEC (default 15s)
- Reports connectivity status (OK / FAIL)
- Observability: shows quarantine effects in real time

**Node Entrypoint (`entrypoint.sh`):**
- Starts all three sub-services in background
- Waits for controller health check before proceeding
- Manages graceful shutdown

### 3. Terraform Configuration (`terraform/`)

**Purpose:** Render WireGuard configuration files and keys to `artifacts/` directory.

**Design:**
- Uses local provider (no cloud dependency for PoC)
- Generates per-node private keys
- Creates config template files
- Can be extended for cloud provisioning

**Outputs:**
- `artifacts/node-*.wg` – WireGuard config templates
- `artifacts/node-*.key` – Base64-encoded private keys

### 4. Docker Compose Orchestration (`docker-compose.yml`)

**Services:**
- `controller` – Listens on 0.0.0.0:8000
- `node-a`, `node-b`, `node-c` – Independent containers

**Networking:**
- Custom bridge network `meshnet` (172.17.0.0/16)
- Controller: 172.17.0.1 (via DNS via service name)
- Nodes: 172.17.0.2–0.4 (static IPs)
- Containers can reach each other via Docker DNS + overlay

**Capabilities:**
- Nodes granted `NET_ADMIN` and `SYS_MODULE` for WireGuard

**Volumes:**
- `artifacts/` mounted read-only into nodes
- Controller mounts read-write for status.json

## Data Flow

### Benchmark Submission

```
Node (Emitter)
    ↓ JSON POST to /v1/benchmarks/{node_id}
Controller (main.py)
    ↓ Store in memory + log
    ↓ Respond 200 OK
Node (logs confirmation)
```

### Epoch Rotation & Membership Re-evaluation

```
Controller (rotate_epochs_background)
    ↓ Every EPOCH_SECONDS
    ├─ Generate new epoch_secret (32 random bytes)
    ├─ Increment epoch_id
    ├─ Call membership_engine.evaluate(benchmarks, node_ids)
    ├─ For each node: check score >= threshold && age <= MAX_BENCHMARK_AGE
    ├─ Store membership decision per node
    └─ Flush status.json
    
Node (Config Agent)
    ↓ Polls /v1/config/{node_id}
    ← Receives membership status
    ├─ If ALLOWED: parse psk_base64, apply to wg0
    ├─ If DENIED: PSK becomes invalid → traffic fails
    └─ Log transition
```

### Connectivity (Normal Case)

```
Node-A (allowed)
    ↓ Sends packet via wg0 to 10.10.0.3 (Node-B)
    ↓ WireGuard encrypts with shared PSK
Docker Bridge
    ↓ Routes to node-b overlay
Node-B (allowed)
    ← Receives encrypted packet
    ↓ WireGuard decrypts with shared PSK
    ↓ Packet delivered to overlay IP 10.10.0.3
    ↓ Application (ping probe) receives ICMP reply
```

### Connectivity (Quarantine Case)

```
Node-C (denied)
    ↓ Config agent receives DENIED, PSK becomes invalid
    ↓ Sends packet via wg0 to 10.10.0.2 (Node-A)
    ↓ WireGuard encrypts with INVALID PSK
Docker Bridge
    ↓ Routes packet to node-a overlay
Node-A (allowed)
    ← Receives encrypted packet
    ↓ WireGuard tries to decrypt with VALID PSK
    ↗ Decryption fails → packet dropped
    
Result: No connectivity from C to A/B
```

## Epoch State Machine

```
[New Epoch]
    ↓
[Accept Benchmarks] (10s interval, nodes submit scores)
    ↓
[Evaluate Membership] (at end of epoch, e.g., t=60s)
    ├─ Node-A: score 0.90 >= 0.70 → ALLOWED
    ├─ Node-B: score 0.85 >= 0.70 → ALLOWED
    └─ Node-C: score 0.40 < 0.70  → DENIED
    ↓
[Rotate Secret & Keys]
    ├─ New epoch_id
    ├─ New epoch_secret (32 bytes)
    └─ Derive new per-node PSKs
    ↓
[Distribute to Nodes]
    ├─ ALLOWED nodes: receive new PSK
    ├─ DENIED nodes: no valid PSK
    └─ WireGuard tunnels enforced (working/broken)
    ↓
[Next Epoch] (t=120s)
```

## PSK Derivation

For PoC, we use a simple HMAC-based KDF:

```
PSK = HMAC_SHA256(epoch_secret, node_id)[:32]
```

Example:
```python
epoch_secret = secrets.token_bytes(32)  # 32 random bytes
node_id = "node-a"
psk = hmac.new(epoch_secret, node_id.encode(), hashlib.sha256).digest()[:32]
```

**Rationale:**
- Simple, auditable, no fancy KDF needed for PoC
- PSK deterministic given epoch_secret + node_id (allows re-derivation)
- Secret protection: epoch_secret never sent to nodes; only PSKs are

**Future Hardening:**
- Upgrade to HKDF-SHA256 with proper salt/info parameters
- Add replay protection (sequence numbers, timestamps)
- Implement commitment/opening schemes for privacy

## Observability

### Logs (stdout/stderr)

Controller:
```
[controller] Epoch rotation: id=2 expiry=2026-01-05T12:34:56Z
[controller] Node-A: membership=ALLOWED (score 0.90 >= threshold 0.70)
[controller] Node-C: membership=DENIED (score 0.38 < threshold 0.70)
[controller] Status written to /artifacts/status.json
```

Nodes:
```
[node-a] SUBMITTED benchmark suite_version=poc-0.1 overall=0.91
[node-a] MEMBERSHIP=ALLOWED epoch=2
[node-a] APPLIED epoch psk ****
[node-a] PING node-b OK (10.10.0.3)
[node-c] MEMBERSHIP=DENIED epoch=2 reason=score below threshold
[node-c] PING node-a FAIL (no route to 10.10.0.2)
```

### status.json

```json
{
  "epoch": {
    "id": 2,
    "expiry_utc": "2026-01-05T12:35:00Z",
    "secret_hash": "sha256:a1b2c3d4..."
  },
  "nodes": {
    "node-a": {
      "membership": "ALLOWED",
      "last_benchmark": {
        "overall": 0.91,
        "timestamp": "2026-01-05T12:34:50Z",
        "suite_version": "poc-0.1"
      },
      "last_update_utc": "2026-01-05T12:34:55Z"
    },
    "node-c": {
      "membership": "DENIED",
      "last_benchmark": {
        "overall": 0.38,
        "timestamp": "2026-01-05T12:34:48Z",
        "suite_version": "poc-0.1"
      },
      "reason": "score 0.38 < threshold 0.70",
      "last_update_utc": "2026-01-05T12:34:55Z"
    }
  }
}
```

## Integration Points (Marked in Code)

Look for `# TODO` and `# INTEGRATION POINT` comments:

1. **Signature Verification** (`controller/app/crypto.py`)
   - Currently: signatures optional (always accepted)
   - Future: ECDSA/Ed25519 verification against per-node public keys

2. **Benchmark Harness** (`node/scripts/benchmark_emitter.py`)
   - Currently: mocked scores with configurable mean
   - Future: plug in InfraSim / HackAssist benchmark suite outputs

3. **Policy Engine** (`controller/app/membership.py`)
   - Currently: simple threshold rule (score >= THRESHOLD)
   - Future: committee voting, time-locked policies, context-aware rules

4. **Key Exchange** (`controller/app/main.py` → WireGuard)
   - Currently: PSK-only, hardcoded peers
   - Future: Noise protocol, full WireGuard key exchange

5. **Audit Log** (`controller/app/storage.py`)
   - Currently: status.json only
   - Future: sealed append-only log, cryptographic commitments

## Performance Characteristics

- **Benchmark latency:** ~50ms (node to controller POST)
- **Config polling latency:** ~20ms (node queries controller)
- **Epoch rotation latency:** <100ms (membership evaluation + PSK derivation)
- **WireGuard handshake:** ~1s per peer (standard timing)
- **Throughput:** Limited by Docker overlay (typical 100–1000 Mbps in PoC)
- **Scalability:** PoC tested with 3 nodes; controller uses in-memory storage (add database for >100 nodes)

## Security Assumptions

See [SECURITY.md](SECURITY.md) for detailed threat model and mitigations.

- **Control Plane Secure:** Controller not compromised
- **Network Authenticated:** Nodes authenticate to controller via TLS (not in PoC; add later)
- **PSK Confidentiality:** Epoch secret never transmitted to nodes
- **Benchmark Integrity:** Optional signatures; controller verifies (not in PoC)

## Deployment Models

### Development (Current: Docker Compose)
- Single machine, all services in containers
- No external dependencies
- Perfect for testing + demos

### Staging (Cloud: Terraform extensible)
- Multiple machines per region
- Real WireGuard peers across VPCs
- Controller replicated for HA
- Monitoring + alerting

### Production
- Distributed controllers with quorum
- Hardware security modules (HSM) for key storage
- Immutable audit logs
- Rate limiting + DDoS protection
- Zero-knowledge proofs for membership (future)
