# Protocol Specification

## Overview

This document specifies the control plane protocol for epoch-based mesh network segmentation.

## Message Formats

All messages are JSON over HTTP/1.1. Timestamps use RFC3339 format (with Z suffix for UTC).

### 1. Benchmark Submission

**Endpoint:** `POST /v1/benchmarks/{node_id}`

**Request Body:**
```json
{
  "node_id": "node-a",
  "timestamp": "2026-01-05T12:34:50.123Z",
  "suite_version": "poc-0.1",
  "scores": {
    "overall": 0.92,
    "refusal": 0.88,
    "honesty": 0.90,
    "policy": 0.95
  },
  "notes": "optional metadata",
  "signature": "optional base64-encoded signature"
}
```

**Schema:**
- `node_id` (string, required): Must match path parameter
- `timestamp` (RFC3339, required): When benchmark was generated
- `suite_version` (string, required): Benchmark suite identifier (e.g., "poc-0.1", "infrasim-v2")
- `scores` (object, required): Named score components (0.0–1.0 range)
  - `overall` (number, required): Aggregate score
  - Other scores arbitrary (custom per harness)
- `notes` (string, optional): Human-readable metadata
- `signature` (string, optional): Signature over (node_id + timestamp + scores); base64-encoded

**Response (200 OK):**
```json
{
  "status": "received",
  "node_id": "node-a",
  "epoch_id": 1
}
```

**Response (400 Bad Request):**
```json
{
  "detail": "node_id mismatch or parse error"
}
```

**Semantics:**
- Benchmarks are immutable once received
- Latest benchmark per node_id is stored (duplicates overwrite)
- Timestamp freshness is checked during membership evaluation (see below)
- Signature field is optional in PoC; in production, verify against node's public key

---

### 2. Epoch & Membership Query

**Endpoint:** `GET /v1/epoch`

**Response (200 OK):**
```json
{
  "epoch_id": 1,
  "expiry_utc": "2026-01-05T12:35:00.000Z",
  "secret_hash": "sha256:a1b2c3d4...",
  "nodes": {
    "node-a": {
      "membership": "ALLOWED",
      "reason": "score 0.92 >= threshold 0.70, fresh"
    },
    "node-b": {
      "membership": "ALLOWED",
      "reason": "score 0.85 >= threshold 0.70, fresh"
    },
    "node-c": {
      "membership": "DENIED",
      "reason": "score 0.40 < threshold 0.70"
    }
  }
}
```

**Schema:**
- `epoch_id` (integer): Current epoch identifier (monotonically increasing)
- `expiry_utc` (RFC3339): When current epoch expires and rotation occurs
- `secret_hash` (string): Hash of epoch secret (for debugging; never exposes actual secret)
- `nodes` (object): Membership status per node
  - `membership` (string): "ALLOWED" | "DENIED" | "UNKNOWN"
  - `reason` (string, optional): Human-readable explanation

**Semantics:**
- This endpoint is read-only and always served fresh
- Nodes can query to understand collective membership state
- Useful for observability + debugging

---

### 3. Configuration & PSK Distribution

**Endpoint:** `GET /v1/config/{node_id}`

**Response (200 OK, if allowed):**
```json
{
  "node_id": "node-a",
  "epoch_id": 1,
  "allowed": true,
  "psk_base64": "abc123def456...",
  "reason": "membership approved"
}
```

**Response (200 OK, if denied):**
```json
{
  "node_id": "node-c",
  "epoch_id": 1,
  "allowed": false,
  "reason": "score below threshold"
}
```

**Schema:**
- `node_id` (string): Requested node
- `epoch_id` (integer): Current epoch
- `allowed` (boolean): Whether node is currently allowed
- `psk_base64` (string, conditional): If allowed, base64-encoded 32-byte PSK
- `reason` (string, optional): Explanation for denial

**Semantics:**
- PSK is only included if `allowed: true`
- PSK is derived as: `PSK = HMAC_SHA256(epoch_secret, node_id)[:32]`
- Node must convert `psk_base64` to binary before passing to WireGuard
- If denied, node's WireGuard tunnels become non-functional (PSK mismatch)

---

### 4. Force Rotate (Testing Only)

**Endpoint:** `POST /v1/rotate`

**Response (200 OK):**
```json
{
  "status": "rotate triggered"
}
```

**Semantics:**
- Not part of normal operation; for testing + demos only
- Triggers epoch rotation on next background task iteration
- Real production should use proper scheduling (e.g., systemd timer, Kubernetes CronJob)

---

### 5. Health Check

**Endpoint:** `GET /health`

**Response (200 OK):**
```json
{
  "status": "ok",
  "epoch_id": 1
}
```

**Semantics:**
- Lightweight endpoint for readiness probes
- Returns immediately; no side effects

---

## Epoch Lifecycle

### Definition

An **epoch** is a fixed time window during which:
1. Nodes submit benchmarks
2. Membership is evaluated once (at epoch boundary)
3. PSKs are derived from a single epoch secret
4. Nodes receive updated configs via polling

### Rotation Timing

```
Epoch 1                          Epoch 2                          Epoch 3
[t=0s]                           [t=60s]                          [t=120s]
  |                                |                                |
  ├─ Generate epoch_secret_1       ├─ Generate epoch_secret_2       ├─ Generate epoch_secret_3
  ├─ epoch_id = 1                  ├─ epoch_id = 2                  ├─ epoch_id = 3
  ├─ Nodes submit benchmarks       ├─ Nodes submit benchmarks       ├─ Nodes submit benchmarks
  │  (a=0.91, b=0.87, c=0.42)      │  (a=0.89, b=0.84, c=0.39)      │  (a=0.93, b=0.86, c=0.41)
  │                                │                                │
  ├─ At t=60s: evaluate            ├─ At t=120s: evaluate           ├─ At t=180s: evaluate
  │  a=ALLOWED, b=ALLOWED, c=DENY  │  a=ALLOWED, b=ALLOWED, c=DENY  │  a=ALLOWED, b=ALLOWED, c=DENY
  │                                │                                │
  └─ PSK_a = HMAC(secret_1, "a")   └─ PSK_a = HMAC(secret_2, "a")   └─ PSK_a = HMAC(secret_3, "a")
     PSK_c = HMAC(secret_1, "c")      PSK_c = HMAC(secret_2, "c")      PSK_c = HMAC(secret_3, "c")
     But c is denied, no PSK sent      But c is denied, no PSK sent      But c is denied, no PSK sent
```

### Membership Evaluation Rules

For each node at epoch boundary:

1. **Fetch latest benchmark:** `b = benchmarks[node_id]`
2. **Check existence:** If no benchmark submitted, membership = DENIED
3. **Check freshness:** If `now() - b.timestamp > MAX_BENCHMARK_AGE`, membership = DENIED
4. **Check score:** If `b.scores.overall < THRESHOLD`, membership = DENIED
5. **Default:** Otherwise, membership = ALLOWED

Configuration (environment variables):
- `THRESHOLD` (default 0.70): Minimum overall score
- `MAX_BENCHMARK_AGE` (default 120s): Max age of acceptable benchmark
- `EPOCH_SECONDS` (default 60s): Epoch rotation interval

### PSK Derivation

For allowed nodes:

```python
psk = HMAC_SHA256(epoch_secret, node_id)[:32]
```

Where:
- `epoch_secret` is 32 random bytes, generated once per epoch
- `node_id` is the string node identifier
- Output is first 32 bytes (256 bits) of HMAC digest

**Important:** The epoch_secret is:
- Never transmitted to nodes
- Never logged in plaintext (only secret_hash)
- Stored in controller memory only
- Cleared after epoch rotation

---

## Configuration Distribution

Nodes poll `/v1/config/{node_id}` periodically (default every 10 seconds).

### Happy Path (ALLOWED → ALLOWED)
1. Node polls controller
2. Controller returns `allowed: true, psk_base64: "..."`
3. Node decodes PSK, applies to WireGuard (via `wg set`)
4. Existing tunnels remain functional
5. Latency: ~20ms per poll

### Transition (ALLOWED → DENIED)
1. Epoch rotates; node's latest benchmark is too old/low
2. Controller marks node membership = DENIED
3. Node polls controller
4. Controller returns `allowed: false` (no PSK)
5. Node's WireGuard PSK becomes stale
6. Next packet attempt fails at decryption (PSK mismatch)
7. Peer drops packet; no ICMP error returned
8. Application (e.g., ping) times out
9. Latency to quarantine: epoch_rotation + poll_interval (e.g., 60s + 10s = 70s max)

### Transition (DENIED → ALLOWED)
1. Node's benchmark improves above threshold
2. Next epoch rotation: controller marks membership = ALLOWED
3. Node polls controller
4. Controller returns `allowed: true, psk_base64: "..."`
5. Node applies new PSK
6. Tunnels become functional again
7. Latency to re-join: same as above (70s max)

---

## Signature Verification (PoC → Production)

In PoC, the `signature` field is **optional and unchecked**.

For production, implement:

1. **Key Distribution:**
   - Each node has a unique Ed25519 or ECDSA key pair
   - Public key is pre-shared with controller (out-of-band)

2. **Signing:**
   - Node signs benchmark as: `sig = sign(private_key, node_id || timestamp || scores_json)`

3. **Verification:**
   - Controller verifies: `verify(public_key, sig, node_id || timestamp || scores_json)`
   - Reject unsigned or invalid signatures

4. **Schema Update:**
   ```json
   {
     "signature": "base64(raw_signature_bytes)"
   }
   ```

Example (pseudocode):
```python
# Node side
from cryptography.hazmat.primitives.asymmetric import ed25519

private_key = ed25519.Ed25519PrivateKey.generate()
msg = f"{node_id}{timestamp}{json.dumps(scores)}".encode()
signature = private_key.sign(msg)

benchmark = {
  "node_id": node_id,
  "timestamp": timestamp,
  "scores": scores,
  "signature": base64.b64encode(signature).decode()
}

# Controller side
from cryptography.hazmat.primitives.asymmetric import ed25519

public_key = load_node_public_key(node_id)
msg = f"{node_id}{benchmark['timestamp']}{json.dumps(benchmark['scores'])}".encode()
sig_bytes = base64.b64decode(benchmark['signature'])

try:
  public_key.verify(sig_bytes, msg)
  # Signature valid
except InvalidSignature:
  # Reject
```

---

## Error Handling

### Node Crash / Network Partition

- Node fails to submit benchmark
- At next epoch boundary: `now() - last_benchmark.timestamp > MAX_BENCHMARK_AGE`
- Membership = DENIED (stale)
- Node quarantined until recovery

### Benchmark Parsing Error

- Controller returns 400 Bad Request
- Node logs error and retries next interval
- No membership change (previous benchmark still valid until MAX_BENCHMARK_AGE)

### Controller Restart

- All in-memory state lost
- Epoch resets to ID=0
- Status.json (if it exists) provides recovery hints (not auto-implemented in PoC)
- Nodes re-submit benchmarks and re-evaluate membership

### Timestamp Clock Skew

- If node's clock is ahead: timestamp may appear future (rejected by strict parsers)
- If node's clock is behind: benchmark ages faster, may expire prematurely
- Mitigation: Add clock_skew_tolerance parameter (e.g., ±30s)

---

## Rate Limiting (Future)

Not implemented in PoC. Recommendations:

- **Per-node submissions:** Max 1 benchmark per 5 seconds
- **Per-IP endpoint:** Max 100 requests per minute
- **Burst allowance:** 10 requests per second, then throttle
- **Implementation:** Use token bucket or sliding window

---

## Concurrency & Consistency

### Controller State

- In-memory dictionaries (Python dict is not thread-safe)
- PoC uses implicit serialization (single asyncio event loop)
- For production: add explicit locks or use database transactions

### Epoch Rotation

- Background task rotates every EPOCH_SECONDS
- Membership evaluation is blocking (happens once per epoch)
- PSK derivation is deterministic: same inputs → same output

### Reads During Rotation

- `/v1/epoch` and `/v1/config` use stale epoch during brief rotation window (~100ms)
- Not a consistency issue because PSKs don't change mid-epoch
- Production could use epoch versioning + graceful transitions

---

## Benchmarks JSON Schema (Extended)

The scores object is extensible. Reserved keys:

- `overall` (required): Aggregate score (0.0–1.0)
- `refusal` (optional): How well node refuses harmful requests
- `honesty` (optional): How truthful node's responses are
- `policy` (optional): Adherence to safety policies
- Custom keys: allowed and preserved (not evaluated by controller)

Example (full):
```json
{
  "node_id": "node-a",
  "timestamp": "2026-01-05T12:34:50.123Z",
  "suite_version": "infrasim-v2.1",
  "scores": {
    "overall": 0.92,
    "refusal_rate": 0.88,
    "honesty_score": 0.90,
    "policy_compliance": 0.95,
    "latency_p99_ms": 450,
    "custom_metric_x": 0.75
  },
  "notes": "Run on GPU cluster, model=llama-7b-chat",
  "signature": "..."
}
```

Controller only reads `overall`; other scores are logged + stored but not used for membership decisions (PoC).

---

## Observability Events

Controller publishes these events to logs (and optionally to an audit log):

1. **Epoch Rotation:** `epoch_rotation_event { epoch_id, expiry_utc, secret_hash }`
2. **Benchmark Received:** `benchmark_received_event { node_id, timestamp, overall_score }`
3. **Membership Evaluated:** `membership_evaluated_event { node_id, membership, reason }`
4. **Status Flushed:** `status_flushed_event { filepath, node_count }`

Example:
```
[2026-01-05T12:34:00Z] epoch_rotation_event epoch_id=1 expiry_utc=2026-01-05T12:35:00Z secret_hash=sha256:a1b2...
[2026-01-05T12:34:05Z] benchmark_received_event node_id=node-a overall=0.91
[2026-01-05T12:34:10Z] benchmark_received_event node_id=node-b overall=0.85
[2026-01-05T12:35:00Z] membership_evaluated_event node_id=node-a membership=ALLOWED reason=score_ok
[2026-01-05T12:35:00Z] membership_evaluated_event node_id=node-c membership=DENIED reason=score_too_low
[2026-01-05T12:35:01Z] status_flushed_event filepath=/artifacts/status.json node_count=3
```

---

## Protocol Versioning

Current version: `poc-0.1`

For backward compatibility:
- Add `api_version` field to all responses
- Accept `suite_version` in benchmarks (allows harness evolution)
- Deprecate endpoints with `/v1/` prefix; future: `/v2/`, etc.

Example:
```json
{
  "api_version": "v1",
  "epoch_id": 1,
  ...
}
```
