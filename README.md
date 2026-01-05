# aligned-meshnet-poc

A minimal proof-of-concept demonstrating how behavioral benchmark outputs drive enforced segmentation and rotating membership in a WireGuard-based mesh VPN.

**Goal:** Show in ~5 minutes how nodes scoring above a behavioral threshold stay connected, while low-scoring nodes are automatically quarantined via PSK rotation.

## Key Features

- **Behavioral Scoring:** Mocked benchmark emitter on each node produces JSON scores
- **Adaptive Membership:** Controller enforces segmentation based on per-node benchmark freshness and threshold
- **Epoch-Based Key Rotation:** Shared epoch secrets rotate every 60 seconds; PSKs are derived per-node
- **Quarantine Mechanism:** Low-scoring nodes lose tunnel connectivity when their PSK is invalidated
- **Local Demo:** Runs entirely on Docker Compose; no cloud credentials needed
- **Observable:** Logs and status.json show membership decisions in real-time

## Threat Model

This PoC addresses scenarios where:
- **Sybil attacks:** Nodes must continuously demonstrate aligned behavior to stay in the mesh
- **Free-riding:** Low-performing nodes cannot drain resources from good actors
- **Drift:** Misbehavior is detected and penalized within one epoch cycle
- **Eavesdropping:** WireGuard tunnels encrypt mesh traffic (no mitigation for compromised nodes)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Mesh Controller                         │
│  (FastAPI)                                                   │
│  • Maintains epoch state (epoch_id, secret, expiry)         │
│  • Receives benchmark submissions from nodes                │
│  • Evaluates membership: score >= threshold && fresh        │
│  • Derives PSKs via HKDF(epoch_secret, node_id)             │
│  • Rotates epoch every EPOCH_SECONDS                        │
│  • Publishes status.json                                    │
└─────────────────────────────────────────────────────────────┘
           ↓
    ┌──────┴──────┬────────┐
    ↓             ↓        ↓
  Node-A      Node-B    Node-C
  (WireGuard)  (WireGuard) (WireGuard)
  • Benchmark emitter
  • Config agent (polls controller)
  • WireGuard tunnel (wg0)
  • Network probe (ping peers)
```

## Quick Start

### Requirements
- Docker & Docker Compose
- GNU Make
- Terraform (for local file rendering)
- ~500MB disk, 2GB RAM

### Run the Demo

```bash
# Clone repo
git clone https://github.com/yourusername/aligned-meshnet-poc.git
cd aligned-meshnet-poc

# Start local demo: terraform apply (local) + docker compose up
make demo

# Watch logs (opens tail on controller + nodes)
make logs

# Force epoch rotation before default 60s
make rotate-now

# Stop containers
make down
```

### Expected Behavior (Demo Scenario)

1. **Initialization (t=0-10s)**
   - Controller starts, nodes join
   - Each node posts initial benchmark score
   - Node-A: mean ~0.90 (good)
   - Node-B: mean ~0.85 (good)
   - Node-C: mean ~0.40 (bad – will be quarantined)

2. **First Epoch (t=0-60s)**
   - Controller accepts all three nodes (first epoch is permissive)
   - Nodes receive PSK, configure WireGuard, test pings
   - Logs show "MEMBERSHIP=ALLOWED" for all

3. **Epoch Rotation (t=60s)**
   - Controller generates new epoch secret
   - Evaluates membership:
     - Node-A: overall_score=0.90 >= THRESHOLD (0.70) → **ALLOWED**
     - Node-B: overall_score=0.85 >= THRESHOLD (0.70) → **ALLOWED**
     - Node-C: overall_score=0.40 < THRESHOLD (0.70) → **DENIED**
   - Node-C receives new PSK that doesn't match → pings fail

4. **Post-Quarantine (t=60-120s)**
   - Node-C keeps emitting benchmarks but still denied
   - A+B continue communicating
   - status.json shows Node-C as QUARANTINED

## Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) – System design, components, interfaces
- [PROTOCOL.md](docs/PROTOCOL.md) – Epoch rotation, membership rules, config distribution
- [SECURITY.md](docs/SECURITY.md) – Assumptions, limitations, hardening roadmap
- [INTEGRATION.md](docs/INTEGRATION.md) – How to plug in real benchmark harnesses (InfraSim, HackAssist)
- [DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) – 5-minute demo talking points and commands

## Repository Structure

```
aligned-meshnet-poc/
├── README.md                     # This file
├── LICENSE                       # Apache-2.0
├── Makefile                      # make demo, make down, make logs
├── docker-compose.yml            # Controller + Node-A, B, C
├── .env.example                  # Environment variables
├── .gitignore                    # Ignore artifacts/
├── controller/
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py              # FastAPI server
│   │   ├── membership.py        # Membership logic + threshold
│   │   ├── crypto.py            # HKDF PSK derivation
│   │   └── storage.py           # State management (in-memory + JSON)
│   ├── requirements.txt
│   └── tests/
│       └── test_membership.py
├── node/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── scripts/
│       ├── benchmark_emitter.py  # Periodic JSON score generator
│       ├── config_agent.py       # Polls controller for PSK/config
│       └── net_probe.sh          # Ping network peers
├── terraform/
│   ├── README.md
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── modules/
│       └── wg_config/
│           ├── main.tf          # WireGuard key/config generation
│           ├── variables.tf
│           └── outputs.tf
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PROTOCOL.md
│   ├── SECURITY.md
│   ├── INTEGRATION.md
│   └── DEMO_SCRIPT.md
└── artifacts/                    # .gitignored; generated at runtime
    ├── node-a.wg
    ├── node-b.wg
    ├── node-c.wg
    ├── controller.env
    └── status.json

```

## Configuration

Edit `.env.example` to tune:

```bash
# Membership threshold (0.0–1.0)
THRESHOLD=0.70

# Epoch rotation interval (seconds)
EPOCH_SECONDS=60

# Max age of benchmark before expiry (seconds)
MAX_BENCHMARK_AGE=120

# Number of nodes
NUM_NODES=3

# Node score mean (per node via docker-compose env)
NODE_A_SCORE_MEAN=0.90
NODE_B_SCORE_MEAN=0.85
NODE_C_SCORE_MEAN=0.40
```

## Logs & Observability

### Controller logs
```
[controller] Epoch rotation: id=1 expiry=2026-01-05T12:34:56Z
[controller] Node-A: score=0.91, membership=ALLOWED
[controller] Node-C: score=0.38, membership=DENIED (too low)
[controller] Status written to /artifacts/status.json
```

### Node logs
```
[node-a] SUBMITTED benchmark suite_version=poc-0.1 overall=0.91
[node-a] MEMBERSHIP=ALLOWED
[node-a] APPLIED epoch psk ****
[node-a] PING node-b OK (172.17.0.10)
[node-a] PING node-c FAIL (no route)
```

### status.json
```json
{
  "epoch": {
    "id": 1,
    "expiry_utc": "2026-01-05T12:34:56Z",
    "secret_hash": "sha256:..."
  },
  "nodes": {
    "node-a": {
      "membership": "ALLOWED",
      "last_benchmark": { "overall": 0.91, "timestamp": "..." },
      "psk": "valid"
    },
    "node-c": {
      "membership": "DENIED",
      "last_benchmark": { "overall": 0.38, "timestamp": "..." },
      "reason": "score below threshold"
    }
  }
}
```

## Troubleshooting

**Containers won't start:**
```bash
# Check Docker
docker ps -a
docker logs $(docker ps -aqf "name=controller")
```

**Nodes can't ping:**
- Ensure WireGuard interfaces are up: `docker exec node-a ip addr show wg0`
- Check PSK: `docker exec node-a wg show wg0`
- Watch logs: `make logs`

**Terraform fails:**
```bash
# Reset artifacts
rm -rf artifacts/
terraform init -chdir=terraform
terraform apply -chdir=terraform -auto-approve
```

**Epoch not rotating:**
- Check EPOCH_SECONDS in .env (default 60s)
- Controller logs should show rotation every 60s
- Force rotation: `make rotate-now`

## Next Steps (Future Hardening)

1. **Add Signatures & Identity:**
   - Implement ECDSA or Ed25519 signatures on benchmark submissions
   - Controller verifies sig against per-node public key
   - See: [SECURITY.md](docs/SECURITY.md#future-hardening)

2. **Integrate Real Benchmark Harness:**
   - Plug in InfraSim or HackAssist benchmark outputs
   - Map benchmark suite results to score aggregate
   - See: [INTEGRATION.md](docs/INTEGRATION.md)

3. **Distributed Membership (Committees):**
   - Replace single-controller with n-of-m quorum
   - Requires consensus + sealed audit log
   - Prevents controller compromise

4. **Replay Protection & Audit Log:**
   - Sequence numbers on all control messages
   - Immutable append-only log of membership changes
   - Support forensic audit

5. **Multi-Segment Routing by Policy:**
   - Allow nodes to specify policy class (e.g., "training", "inference")
   - Controller creates separate WireGuard tunnels per class
   - Fine-grained segmentation per workload

6. **Hardened WireGuard Setup:**
   - Current PoC: PSK-only; upgrade to full key exchange + public key pinning
   - Add replay detection and timing obfuscation
   - Consider WireGuard over QUIC for routing friendliness

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Citation & Acknowledgments

This PoC was designed for the alignment safety + infrastructure control plane community. Inspired by defensive isolation patterns and behavioral filtering in mesh networks.

---

**Questions?** Open an issue or contact the maintainers.

**Want to contribute?** See [SECURITY.md](docs/SECURITY.md#responsible-disclosure) for guidelines.
# worktest
