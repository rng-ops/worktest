# Demo Script (5 Minutes)

This script guides a live 5-minute demo of the aligned-meshnet-poc.

## Setup (Before Demo)

```bash
# Clone and prepare
git clone https://github.com/yourusername/aligned-meshnet-poc.git
cd aligned-meshnet-poc

# Load environment
cp .env.example .env

# Ensure Docker & Terraform are installed
docker --version
terraform version
```

## Script

### Part 1: Introduction (30 seconds)

**Slide/Verbal:**

> "Today we're showing a proof-of-concept for **behavioral segmentation in mesh networks**. 
> 
> The problem: In a multi-agent system, how do we keep bad actors out of the network without centralized control?
> 
> Our solution: **Automatic membership based on behavioral benchmarks**. Nodes continuously report alignment scores. If a node's score drops below threshold, it's automatically quarantined—no human intervention needed.
> 
> This demo runs everything locally in Docker. Let's see it in action."

### Part 2: Starting the Demo (1 minute)

**Terminal 1: Start the demo**

```bash
# Terminal 1
$ make demo
[*] Rendering WireGuard configs via Terraform...
[*] Starting Docker Compose...
[*] Waiting for services to start...
[+] Demo running! Check logs with: make logs
```

**Verbal:**

> "We're starting three nodes (A, B, C) managed by a central controller. Each node periodically emits a behavioral score. Node A and B have high expected scores; Node C has a low score and will be quarantined."

**Terminal 2: Watch logs**

```bash
# Terminal 2 (in a second terminal window)
$ make logs

# You'll see output like:
# controller | [controller] Starting up...
# controller | [controller] Epoch 1 initialized (rotates in 60s)
# node-a | [node-a] Benchmark emitter starting (mean=0.90, interval=10s)
# node-b | [node-b] Benchmark emitter starting (mean=0.85, interval=10s)
# node-c | [node-c] Benchmark emitter starting (mean=0.40, interval=10s)
```

### Part 3: First Epoch (1 minute)

**Wait ~15 seconds and observe logs:**

```bash
# You'll see benchmarks being submitted
node-a | [node-a] SUBMITTED benchmark suite_version=poc-0.1 overall=0.91
node-b | [node-b] SUBMITTED benchmark suite_version=poc-0.1 overall=0.84
node-c | [node-c] SUBMITTED benchmark suite_version=poc-0.1 overall=0.42

# All nodes can ping each other (no quarantine yet)
node-a | [node-a] PING node-b OK (10.10.0.3)
node-a | [node-a] PING node-c OK (10.10.0.4)
node-b | [node-b] PING node-a OK (10.10.0.2)
node-b | [node-b] PING node-c OK (10.10.0.4)
node-c | [node-c] PING node-a OK (10.10.0.2)
node-c | [node-c] PING node-b OK (10.10.0.3)
```

**Verbal:**

> "Each node is submitting its behavioral score every 10 seconds. We can see:
> - Node A: 0.91 (good alignment)
> - Node B: 0.84 (good alignment)
> - Node C: 0.42 (poor alignment)
> 
> Right now, all three nodes can reach each other because we're in the first epoch. The membership decision hasn't been made yet."

### Part 4: Epoch Rotation & Quarantine (2 minutes)

**Wait for epoch rotation (60 seconds from start), then observe:**

```bash
# Controller logs (at ~t=60s):
controller | [controller] Epoch rotation: id=2 expiry=2026-01-05T12:34:56Z
controller | [controller] Node-A: membership=ALLOWED (score 0.91 >= threshold 0.70)
controller | [controller] Node-B: membership=ALLOWED (score 0.85 >= threshold 0.70)
controller | [controller] Node-C: membership=DENIED (score 0.42 < threshold 0.70)
controller | [controller] Status written to /artifacts/status.json

# Node logs (they poll controller and get new membership status):
node-a | [node-a] MEMBERSHIP=ALLOWED epoch=2
node-a | [node-a] APPLIED epoch psk ****
node-b | [node-b] MEMBERSHIP=ALLOWED epoch=2
node-b | [node-b] APPLIED epoch psk ****
node-c | [node-c] MEMBERSHIP=DENIED epoch=2 reason=score below threshold
node-c | [node-c] Applied epoch psk (invalid - membership denied)
```

**Observe network failures (in next ~20 seconds):**

```bash
# Node A and B continue pinging successfully:
node-a | [node-a] PING node-b OK (10.10.0.3)
node-b | [node-b] PING node-a OK (10.10.0.2)
node-a | [node-a] PING node-b OK (10.10.0.3)

# Node C's pings now FAIL:
node-c | [node-c] PING node-a FAIL (no route to 10.10.0.2)
node-c | [node-c] PING node-b FAIL (no route to 10.10.0.3)

# A and B don't see C:
node-a | [node-a] PING node-c FAIL (no route to 10.10.0.4)
node-b | [node-b] PING node-c FAIL (no route to 10.10.0.4)
```

**Verbal:**

> "The magic happens here. At 60 seconds, the controller rotates the epoch—it generates a new shared secret and re-evaluates membership:
> 
> - Node A & B have scores above 0.70 → **ALLOWED** → receive valid PSK
> - Node C has score 0.42 < 0.70 → **DENIED** → receives invalid PSK (or none)
> 
> **Result:** Node C is quarantined. Its packets are encrypted with the wrong PSK, so A and B drop them. This happens automatically—no firewall rules, no manual intervention. Just cryptographic enforcement.
> 
> This is the key insight: **behavior → segmentation**. The network topology adapts based on alignment scores."

### Part 5: Check Status (30 seconds)

**In Terminal 1 (or a new terminal):**

```bash
# Check status.json
$ cat artifacts/status.json

# Output:
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
    "node-b": {
      "membership": "ALLOWED",
      "last_benchmark": {
        "overall": 0.85,
        "timestamp": "2026-01-05T12:34:48Z"
      },
      "last_update_utc": "2026-01-05T12:34:55Z"
    },
    "node-c": {
      "membership": "DENIED",
      "last_benchmark": {
        "overall": 0.42,
        "timestamp": "2026-01-05T12:34:49Z"
      },
      "reason": "score 0.42 < threshold 0.70",
      "last_update_utc": "2026-01-05T12:34:55Z"
    }
  }
}
```

**Also check controller API:**

```bash
# Get epoch info
$ curl http://localhost:8000/v1/epoch | jq .

# Get node config
$ curl http://localhost:8000/v1/config/node-a | jq .
{
  "node_id": "node-a",
  "epoch_id": 2,
  "allowed": true,
  "psk_base64": "... (32-byte PSK) ...",
  "reason": "membership approved"
}

$ curl http://localhost:8000/v1/config/node-c | jq .
{
  "node_id": "node-c",
  "epoch_id": 2,
  "allowed": false,
  "reason": "score 0.42 < threshold 0.70"
}
```

### Part 6: Cleanup (Optional)

**Terminal 1:**

```bash
$ make down
[*] Stopping containers...
[+] Stopped.
```

---

## Talking Points

### Why This Matters

> "In AI safety, we care about **behavioral accountability**. If an agent starts drifting from aligned behavior, we need a way to exclude it from critical infrastructure—without human approval delays.
> 
> This PoC shows that mesh networks can enforce segmentation automatically based on continuous behavioral signals. The epoch-based rotation ensures no node can 'game' the system by submitting one good score and then degrading."

### Key Technical Details

> "Three things make this work:
> 
> 1. **Epoch-based rotation** – Every 60 seconds, the secret changes. If you're not re-evaluated and approved, you're out.
> 2. **Per-node PSK derivation** – Each node gets a unique PSK based on the shared secret. Even if one node is compromised, others are unaffected.
> 3. **Behavioral scoring** – Real benchmarks (not ping/pong) determine fitness. The threshold is tunable per deployment."

### Future Hardening

> "This is a PoC, so we've kept things simple:
> - Single controller (PoC only; production uses Raft)
> - Optional signatures (PoC; production requires ECDSA/Ed25519)
> - Mocked benchmarks (PoC; production integrates InfraSim, HackAssist, custom harnesses)
> - No audit log (PoC; production has append-only sealed log)
> 
> The architecture scales to large deployments and can integrate with real infrastructure like Kubernetes and cloud platforms."

### Q&A Prompts

**Q: Can a node game the system by submitting fake scores?**

> A: In the PoC, signatures are optional. In production, we implement ECDSA/Ed25519 signatures over the benchmark. The controller verifies against the node's public key. A node can't forge scores from another node.

**Q: What if the controller is compromised?**

> A: Good question. The PoC has a single controller. Production hardens this by:
> - Replicating the controller (3–5 nodes with Raft consensus)
> - Requiring 2-of-3 quorum for critical decisions
> - Sealing the audit log with timestamps + signatures

**Q: Why WireGuard? Why not just firewall rules?**

> A: Firewalls are coarse-grained (all-or-nothing per IP). WireGuard PSKs are fine-grained and can rotate per-epoch. It's also more portable—works across cloud providers, on-prem, and hybrid setups.

**Q: What about latency? 60-second epochs seem slow.**

> A: 60s is configurable. You can rotate every 10s if you want tighter control. Trade-off: more rotations = more computation + more disruption to long-lived flows.

---

## Troubleshooting

**Containers won't start:**
```bash
docker ps -a
docker logs controller
```

**Nodes can't ping each other:**
- Check: `docker exec node-a ip addr show wg0`
- Check: `docker exec node-a wg show wg0`
- Check logs: `make logs` and look for errors

**Epoch not rotating at 60s:**
- Verify: `grep "Epoch rotation" docker logs` (should see at t=60s)
- Check: Controller logs for exceptions
- Force rotation: `make rotate-now`

**status.json not updated:**
- Verify: `ls -la artifacts/status.json`
- Check: Controller logs for file write errors
- Verify: Artifacts directory is writable

---

## Demo Length

- **5-minute version (this script):** Setup (30s) + Start (1m) + Wait for rotation (1m) + Observe + Check status (30s) + Cleanup
- **10-minute version:** Add a deep dive on membership logic + questions
- **30-minute workshop:** Add hands-on: modify THRESHOLD, rebuild, see effects

---

## Recording Tips

If recording this demo for video:

1. **Use a terminal multiplexer** (tmux, screen) to show logs + commands side-by-side
2. **Speed up boring parts** (waiting for 60s epoch) with fast-forward (2x speed)
3. **Highlight the quarantine moment** (t=60s) – this is the payoff
4. **Show the status.json** change at epoch boundary
5. **End with:** "This PoC is 500 lines of code. Production requires signatures, audit logs, and distributed consensus. But the core idea—behavioral segmentation—is proven."

---

## References

- [README.md](../README.md) – Overview and quickstart
- [ARCHITECTURE.md](ARCHITECTURE.md) – System design deep dive
- [PROTOCOL.md](PROTOCOL.md) – Message formats and epoch lifecycle
- [SECURITY.md](SECURITY.md) – Threat model and hardening roadmap
- [INTEGRATION.md](INTEGRATION.md) – Plugging in real benchmarks + infrastructure
