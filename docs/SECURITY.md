# Security

## Threat Model

This section details threats, assumptions, and mitigations.

### Assumptions (Must Hold)

1. **Controller is trusted:** Not compromised, code is reviewed, deployment is secure
2. **Control channel is authenticated:** Future: add TLS mutual auth between nodes + controller
3. **Benchmark integrity:** Nodes honestly report their behavioral scores (PoC; implement signatures for prod)
4. **Network isolation:** Mesh overlay is isolated from critical infrastructure
5. **Cryptographic primitives:** HMAC-SHA256 and WireGuard are secure

### Threat: Sybil Attack

**Description:** Attacker creates many fake nodes to gain influence or bypass scoring rules.

**PoC Mitigation:**
- Each node must submit benchmarks and be evaluated individually
- Low-scoring nodes are quarantined
- No quorum or voting involved (controller decides unilaterally)

**Hardening:**
- Require node identity certificate (X.509 or similar)
- Rate-limit benchmark submissions per identity
- Require whitelist of known node IDs

---

### Threat: Free-Riding / Resource Exhaustion

**Description:** Low-performing node remains in mesh and drains resources from good actors.

**PoC Mitigation:**
- Membership re-evaluated every 60 seconds
- Low-scoring nodes (< threshold) are quarantined within one epoch
- Quarantine = no PSK, no tunnel access

**Effectiveness:** High (60–120s latency to remove bad actors)

**Hardening:**
- Implement bandwidth policing per node
- Add reputation decay (old scores count less)
- Use committees to vote on membership (prevent single controller compromise)

---

### Threat: Behavioral Drift / Gradual Degradation

**Description:** Node slowly becomes misaligned; benchmarks don't capture subtle drift.

**PoC Mitigation:**
- Frequent re-evaluation (every epoch)
- Threshold is configurable (can lower to catch drift earlier)
- Logs show score trends over time

**Hardening:**
- Implement time-series analysis (EWMA, Kalman filter) to detect trend changes
- Add additional signals beyond benchmarks (e.g., latency, error rates)
- Use anomaly detection (isolation forest, DBSCAN)

---

### Threat: Eavesdropping on Control Plane

**Description:** Attacker intercepts benchmark submissions or PSK distributions.

**PoC Mitigation:**
- Docker Compose uses overlay network (not exposed outside containers)
- Localhost-only in development

**Hardening:**
- Add TLS 1.3 to all endpoints
- Mutual TLS (mTLS) with client certificates for nodes
- Encrypt control plane at rest (benchmark storage, status.json)

**Note:** WireGuard data plane is already encrypted (not affected by this threat).

---

### Threat: Compromised Node

**Description:** Attacker gains root on a node container and tries to:
1. Submit fake benchmarks with inflated scores
2. Reverse-engineer PSK or epoch secret
3. Impersonate other nodes

**PoC Mitigation:**
- Signatures are optional (not verified in PoC)
- PSKs are per-node (can't use PSK from one node for another)
- Epoch secret is only in controller memory (not accessible from node)

**Hardening:**
- Implement ECDSA/Ed25519 signatures on benchmarks
- Controller verifies signature against per-node public key
- Add audit log of all membership changes
- Implement key rotation / revocation for compromised node keys
- Use TPM or secure enclave for key storage

---

### Threat: Controller Compromise

**Description:** Attacker gains root on controller and:
1. Modifies membership decisions
2. Learns epoch secrets
3. Forges PSKs

**PoC Mitigation:**
- None (single controller, fully trusted)

**Hardening:**
- Implement controller replication (n-of-m quorum)
- Use Byzantine Fault Tolerant (BFT) consensus (e.g., Raft, PBFT)
- Distribute keys across multiple HSMs
- Require multi-signature authorization for critical operations (e.g., blacklisting all nodes)

---

### Threat: Replay Attack

**Description:** Attacker captures an old benchmark submission and replays it to extend a node's membership.

**PoC Mitigation:**
- Timestamp freshness check (`now() - timestamp <= MAX_BENCHMARK_AGE`)
- Default MAX_BENCHMARK_AGE = 120s (window to re-evaluate)

**Hardening:**
- Add sequence numbers to all messages
- Maintain nonce counter per node
- Log all accepted benchmarks + reject duplicates (exact timestamp match)
- Implement sliding window for timestamp validation (e.g., ±30s tolerance)

---

### Threat: Denial-of-Service (DoS)

**Description:** Attacker floods controller with benchmark submissions or config requests.

**PoC Mitigation:**
- None (no rate limiting)

**Hardening:**
- Implement per-IP and per-node rate limiting
- Use token bucket: 10 requests per node per minute
- Add CAPTCHA or proof-of-work for suspicious sources
- Implement DDoS detection (e.g., NetFlow, anomaly alerts)

---

### Threat: Timing Attacks on PSK Derivation

**Description:** Attacker observes latency of PSK derivation to infer properties of epoch secret.

**PoC Mitigation:**
- HMAC-SHA256 is constant-time (no branch on secret)
- Latency not observable from outside controller

**Hardening:**
- Add dummy operations to mask timing
- Isolate PSK derivation to dedicated CPU core
- Use timing-safe libraries (e.g., libsodium)

---

### Threat: Side-Channel on Ephemeral Keys

**Description:** Attacker uses cache/power analysis to recover epoch secret.

**PoC Mitigation:**
- Docker containers provide process isolation
- No side-channel hardening (PoC level)

**Hardening:**
- Run controller on trusted hardware (Intel SGX, ARM TrustZone)
- Use libsodium (constant-time, audited)
- Add power analysis detection on critical components

---

## Limitations & Known Risks

### 1. Single Point of Failure (Controller)

**Risk:** Controller crash → mesh becomes non-functional.

**Mitigation (PoC):** Documentat only; single container is acceptable for demo.

**Mitigation (Production):** Deploy 3–5 controller replicas with Raft consensus.

---

### 2. No Audit Log

**Risk:** Membership changes not immutable; attacker could cover tracks.

**Mitigation (PoC):** status.json provides observability but can be overwritten.

**Mitigation (Production):** Append-only log (e.g., SQLite in WAL mode, blockchain-lite).

---

### 3. Optional Signatures

**Risk:** Compromised node submits fake scores; controller accepts without verification.

**Mitigation (PoC):** Signatures are optional (noted in code).

**Mitigation (Production):** Mandatory ECDSA/Ed25519 signatures, verified by controller.

---

### 4. Hardcoded PSK Model

**Risk:** If epoch secret leaks, all PSKs are compromised until next rotation.

**Mitigation (PoC):** Epoch rotates every 60s; acceptable for demo.

**Mitigation (Production):** Add "perfect forward secrecy" via key agreement (e.g., HPKE).

---

### 5. No Revocation

**Risk:** If a node is compromised after approval, it remains in the mesh until next benchmark.

**Mitigation (PoC):** Reconfigure THRESHOLD and redeploy (manually trigger rotation).

**Mitigation (Production):** Implement emergency revocation endpoint (requires multiple signatures).

---

### 6. Benchmark Injection (No Time-Series Validation)

**Risk:** Node submits one good benchmark, gets approved; then degrades without further submissions.

**Mitigation (PoC):** MAX_BENCHMARK_AGE = 120s forces re-submission.

**Mitigation (Production):** Require continuous submission; missing benchmark = denial.

---

### 7. Clock Skew

**Risk:** Node with incorrect clock fails freshness check unfairly.

**Mitigation (PoC):** Nodes use Docker container time (synchronized by host).

**Mitigation (Production):** Add NTP synchronization; allow ±30s skew tolerance.

---

## Security Best Practices (Production Roadmap)

### Immediate (MVP)

- [ ] Add TLS to all HTTP endpoints
- [ ] Implement ECDSA signatures on benchmarks
- [ ] Store benchmarks in database (not memory-only)
- [ ] Add audit log to SQLite WAL
- [ ] Rotate epoch key via HKDF with proper salt

### Short-term (1–2 months)

- [ ] Replicate controller (3-node Raft cluster)
- [ ] Implement controller federation (cross-region consensus)
- [ ] Add rate limiting (token bucket per node)
- [ ] Implement node revocation (with multi-signature approval)
- [ ] Add time-series anomaly detection (EWMA, isolation forest)

### Medium-term (3–6 months)

- [ ] Move keys to HSM or secure enclave
- [ ] Implement Byzantine Fault Tolerant (BFT) consensus
- [ ] Add zero-knowledge proofs for membership (zk-SNARK)
- [ ] Implement committee voting (no single controller)
- [ ] Add support for Noise protocol (instead of PSK-only WireGuard)

### Long-term (6–12 months)

- [ ] Integrate with attestation (Intel SGX quotes, ARM TrustZone)
- [ ] Implement accountability proofs (nodes can't deny their scores)
- [ ] Add support for hierarchical policies (sub-meshes, delegated authority)
- [ ] Implement formal verification (Coq, TLA+) of membership logic
- [ ] Standardize protocol (RFC-style specification)

---

## Responsible Disclosure

If you discover a security vulnerability in this PoC:

1. **Do not** open a public issue
2. **Do** email security@example.com with:
   - Vulnerability description
   - Impact assessment
   - Proof of concept (if applicable)
   - Suggested fix (if you have one)
3. Allow 30 days for response
4. Coordinate public disclosure once patch is available

---

## Compliance & Regulations

This PoC is **research-oriented** and **not production-hardened**. Before deploying:

- **Data Privacy:** Benchmark scores may be sensitive; implement GDPR/CCPA controls
- **Export Control:** Cryptographic code may be subject to EAR/ITAR
- **Liability:** Run in isolated environments; document all assumptions

---

## References

- [WireGuard Security Audit](https://www.wireguard.com/papers/wireguard-whitepaper.pdf)
- [OWASP Top 10](https://owasp.org/Top10/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CWE-200: Exposure of Sensitive Information](https://cwe.mitre.org/data/definitions/200.html)

---

## Questions?

Open an issue or contact the maintainers.
