# Chaos Testing Guide — PIVX Testnet6

## Philosophy

Chaos testing in this lab is **protocol-aware and structured**. We do not run
random failures. We run specific scenarios with clear hypotheses, observable
expected outcomes, and recorded results.

Every chaos action:
1. Is logged to `/var/log/pivx/chaos.log` on each affected host
2. Has a corresponding Ansible playbook that can be repeated exactly
3. Should be paired with a Grafana time window annotation or note

---

## Chaos Capabilities

### Control plane

| Action                | Playbook / Make target |
|-----------------------|------------------------|
| Stop cohort           | `make cohort-stop COHORT=tor` |
| Start cohort          | `make cohort-start COHORT=tor` |
| Restart cohort        | `make cohort-restart COHORT=ipv6` |
| Stop provider         | `make provider-stop PROVIDER=contabo` |
| Start provider        | `make provider-start PROVIDER=contabo` |
| Rolling restart       | `make rolling-restart` |

### Network fault injection

| Action                    | Make target |
|---------------------------|-------------|
| Inject latency            | `make chaos-inject-latency COHORT=ipv6 DELAY=200ms` |
| Inject latency + jitter   | *pass via -e: `netem_jitter=20ms`* |
| Inject packet loss        | `make chaos-inject-loss COHORT=tor LOSS=15` |
| Clear netem rules         | `make chaos-clear COHORT=ipv6` |

### Debug collection

```bash
make chaos-collect-debug
# Bundles land in: debug_bundles/<timestamp>/
```

---

## Defined Scenarios

### Scenario 1 — Baseline Healthy Mixed Network

**Purpose**: Confirm all 94 active PIVX instances start and sync, and all 90
masternode instances can form quorum correctly.

**Procedure**:
1. `make deploy`
2. Wait for all instances to sync to chain tip (verify via `make status`)
3. Observe Grafana Fleet Overview: all green
4. Confirm quorum membership: `pivx-cli -conf=... listquorums`

**Expected**: All 94 instances active, quorum forms correctly across the 90
masternode instances.

---

### Scenario 2 — Single Cohort Outage: Tor

**Hypothesis**: Network remains functional when all 30 Tor instances are stopped.
IPv4 and IPv6 masternodes should sustain quorum if they meet the threshold.

**Procedure**:
1. Baseline: `make status`
2. Stop Tor cohort: `make cohort-stop COHORT=tor`
3. Wait 2 minutes
4. Check quorum: `pivx-cli listquorums` on observer
5. Check logs: `{job="pivxd", cohort="ipv4"} |= "quorum"` in Loki
6. Restore: `make cohort-start COHORT=tor`

**Expected**: Quorum degrades gracefully; remaining IPv4+IPv6 DMNs sustain function.
**Record**: Block height progression, quorum counts, DKG status.

---

### Scenario 3 — Single Cohort Outage: IPv6

**Identical to Scenario 2 with COHORT=ipv6.**

---

### Scenario 4 — Single Cohort Outage: IPv4

**Hypothesis**: Network continuity when IPv4 cohort is removed. This is the
most disruptive single-cohort scenario since seed nodes are IPv4 only.

**Note**: Stop Tor + IPv6 seed connectivity is unaffected (seeds are not Tor).

**Procedure**:
1. `make cohort-stop COHORT=ipv4`
2. Observe whether IPv6/Tor instances maintain peer connections
3. Observe DKG state and quorum list
4. Restore after 5 minutes

**Expected**: Partial quorum degradation; test whether Tor+IPv6 alone sustains.

---

### Scenario 5 — Provider Outage: Contabo

**Hypothesis**: Losing the active Contabo provider takes down the current
network. This is a full-provider disaster test for restart and evidence
collection, not a resilience test until OVH/Kimsufi expansion hosts are added.

**Procedure**:
1. `make provider-stop PROVIDER=contabo`
2. Observe quorum status and alert channel
3. Wait 5 minutes
4. Restore: `make provider-start PROVIDER=contabo`

**Expected**: Quorum fails while Contabo is stopped. After future OVH/Kimsufi
hosts are added, this scenario should be updated to test cross-provider
survivability.

---

### Scenario 6 — Seed Node Failure

**Hypothesis**: Loss of all three seed instances does not break existing connections.
New cold-start connections will fail, but established peers maintain.

**Procedure**:
1. Stop PIVX on `tn6-cb1-seed01`, `tn6-cb2-seed02`, and `tn6-cb3-seed03`
2. Restart one masternode instance to see if it reconnects
3. Observe peer counts across fleet

**Expected**: Existing peers persist; restart-reconnection fails until seeds restored.

---

### Scenario 7 — Latency Injection: IPv6 Cohort (200ms)

**Purpose**: Test whether LLMQ timeouts are sensitive to high-latency paths.

**Procedure**:
1. `make chaos-inject-latency COHORT=ipv6 DELAY=200ms`
2. Observe DKG performance over 2x quorum round cycle
3. Check for DKG timeouts in logs: `{cohort="ipv6"} |= "timeout"`
4. `make chaos-clear COHORT=ipv6`

---

### Scenario 8 — Packet Loss: Tor Cohort (15%)

**Purpose**: Test whether Tor instances with simulated unreliable transport
can complete DKG rounds.

**Procedure**:
1. `make chaos-inject-loss COHORT=tor LOSS=15`
2. Observe for 2 DKG cycles
3. Check logs and quorum status
4. Clear: `make chaos-clear COHORT=tor`

---

### Scenario 9 — Combined Partition: IPv6 Down + Tor High Latency

**Purpose**: Simulate a realistic partial degradation where one cohort is offline
and another is impaired.

**Procedure**:
1. `make cohort-stop COHORT=ipv6`
2. `make chaos-inject-latency COHORT=tor DELAY=300ms`
3. Observe quorum for 5 minutes
4. Restore: `make cohort-start COHORT=ipv6 && make chaos-clear COHORT=tor`

---

### Scenario 10 — Rolling Restart

**Purpose**: Verify no quorum disruption from a rolling node restart
(simulates deployments or reboots).

```bash
make rolling-restart
```

3 hosts at a time, with 30s pause between batches.

---

## Collecting Evidence After a Chaos Scenario

Always run after any non-trivial scenario:

```bash
make chaos-collect-debug
```

Bundles land in `debug_bundles/<timestamp>/`. Each host folder contains:
- `getblockchaininfo.json`
- `getpeerinfo.json`
- `mn_list.json`
- `quorum_list.json`
- `dkg_status.json`
- `debug_tail.log` (last 500 lines of PIVX debug log)
- `tc_qdisc.txt` (netem state)
- `systemd_status.txt`
- `journal_1h.txt` (journald last hour)

---

## netem Scope Note

`tc qdisc` rules apply to **all traffic** on the interface, not only PIVX p2p
traffic. This is intentional for realistic simulation. If you need PIVX-only
traffic shaping (e.g., to keep SSH responsive during tests), use TC filters:

```bash
# Example: add PIVX p2p port to a specific class
tc qdisc add dev eth0 root handle 1: prio bands 3
tc filter add dev eth0 protocol ip parent 1: prio 1 \
  u32 match ip dport 51474 0xffff flowid 1:3
tc qdisc add dev eth0 parent 1:3 handle 30: netem delay 200ms
```

Full implementation left to operator — document your filter in this file when used.

---

## Test Log Template

For each scenario, record:

```
Date: 
Scenario: 
Operator: 
Actions taken:
  1. 
  2. 
Observations:
  - Quorum count before:
  - Quorum count after:
  - DKG errors seen:
  - Peer counts:
  - Block height progression:
Conclusion:
Debug bundle: debug_bundles/<timestamp>/
```
