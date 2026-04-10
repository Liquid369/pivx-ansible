# Testnet6 Ansible — Build Review

> Generated: 2026-04-08  
> Use this document to review what was scaffolded, what needs your input before anything runs, and where the highest risks are. Edit inline with your decisions/notes.

---

## Table of Contents

1. [What Was Built](#1-what-was-built)
2. [Repository Tree](#2-repository-tree)
3. [Files to Review First](#3-files-to-review-first)
4. [Assumptions Made](#4-assumptions-made)
5. [Blocking Items (Nothing Runs Without These)](#5-blocking-items-nothing-runs-without-these)
6. [High-Risk Areas](#6-high-risk-areas)
7. [Quick Start Sequence](#7-quick-start-sequence)
8. [Your Notes](#8-your-notes)

---

## 1. What Was Built

A production-quality PIVX Testnet6 quorum testing environment with:

| Category | Count | Notes |
|---|---|---|
| Ansible roles | 15 | common, pivx_install, pivx_instance, tor_hidden_service, node_exporter, vector, **tc_netem**, **pivx_bootstrap_miner**, **pivx_seeder**, **pivx_observer**, prometheus, loki, grafana, alertmanager, alertmanager |
| Playbooks | 27 | site, bootstrap, deploy_pivx, deploy_tor, deploy_monitoring, upgrade_pivx, 7 lifecycle/, 10 chaos/, ops/show_status |
| Host inventories | 15 | tn6-cb1–7, tn6-ovh1–5, tn6-seed01–02, tn6-infra01 |
| Masternode instances | ~36 | mn01–mn36 across 12 node hosts, 3 instances each |
| Protocol cohorts | 3 | IPv4 (cohort_ipv4), IPv6 (cohort_ipv6), Tor (cohort_tor) |
| Docs | 7 | ARCHITECTURE, INVENTORY_MODEL, OBSERVABILITY, CHAOS_TESTING, DEPLOYMENT_PLAN, OPERATIONS, ASSUMPTIONS |
| Runbooks | 4 | upgrade_pivx, rolling_restart, collect_quorum_logs, isolate_cohort |
| Scripts | 3 | generate_stub_host_vars.py, validate_inventory.py, show_layout.py |
| Observability stack | Full | Prometheus + Loki + Grafana + Alertmanager + Vector + node_exporter |

### Fleet layout summary

```
Provider   Hosts    Instances/host   Protocol mix (per host)
---------  -------  ---------------  --------------------------
Contabo    cb1–cb7  3 MNs            1× IPv4, 1× IPv6, 1× Tor
OVH        ovh1–5   3 MNs            1× IPv4, 1× IPv6, 1× Tor
Seeders    seed01–2 1 node each      IPv4 only
Observer   obs01    shared w/ infra  IPv4 only
Infra      infra01  monitoring host  Prometheus/Loki/Grafana/AM
```

---

## 2. Repository Tree

```
testnet6-ansible/
├── ansible.cfg                        ← pipelining, ControlMaster, fact cache
├── Makefile                           ← all operational targets
├── README.md
├── requirements.txt                   ← Python deps for scripts
│
├── ansible/
│   ├── requirements.yml               ← Ansible Galaxy collections
│   ├── inventories/testnet6/
│   │   ├── hosts.yml                  ← master inventory
│   │   ├── group_vars/
│   │   │   ├── all/
│   │   │   │   ├── main.yml           ← *** FILL IN PIVX VERSION/URL HERE ***
│   │   │   │   └── vault.yml.example  ← copy → vault.yml, encrypt
│   │   │   ├── masternodes.yml
│   │   │   ├── seeders.yml
│   │   │   ├── observers.yml
│   │   │   └── monitoring.yml
│   │   └── host_vars/
│   │       ├── tn6-cb1.yml            ← canonical fully-annotated example
│   │       ├── tn6-cb2.yml … tn6-cb7.yml
│   │       ├── tn6-ovh1.yml … tn6-ovh5.yml
│   │       ├── tn6-seed01.yml
│   │       ├── tn6-seed02.yml
│   │       └── tn6-infra01.yml
│   │
│   ├── playbooks/
│   │   ├── site.yml                   ← full bring-up (bootstrap→tor→pivx→monitoring)
│   │   ├── bootstrap.yml
│   │   ├── deploy_pivx.yml
│   │   ├── deploy_tor.yml
│   │   ├── deploy_monitoring.yml
│   │   ├── upgrade_pivx.yml           ← serial:3, graceful stop→install→start
│   │   ├── ops/
│   │   │   └── show_status.yml
│   │   └── chaos/
│   │       ├── stop_cohort.yml
│   │       ├── start_cohort.yml
│   │       ├── restart_cohort.yml
│   │       ├── stop_provider.yml
│   │       ├── start_provider.yml
│   │       ├── inject_latency.yml
│   │       ├── inject_loss.yml
│   │       ├── clear_netem.yml
│   │       ├── rolling_restart.yml
│   │       └── collect_debug.yml
│   │
│   └── roles/
│       ├── common/                    ← OS baseline: NTP, ufw, sysctl, logrotate
│       ├── pivx_install/              ← download + install binary (idempotent)
│       ├── pivx_instance/             ← per-instance: conf + env + systemd unit
│       ├── tor_hidden_service/        ← per-instance torrc + v3 hidden services
│       ├── node_exporter/
│       ├── vector/                    ← journald → Loki log pipeline
│       ├── chaos/                     ← tc/netem inject/clear task files
│       ├── prometheus/                ← scrape config + pivx alert rules
│       ├── loki/
│       ├── grafana/                   ← fleet_overview.json dashboard included
│       └── alertmanager/
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── INVENTORY_MODEL.md
│   ├── OBSERVABILITY.md
│   ├── CHAOS_TESTING.md
│   ├── DEPLOYMENT_PLAN.md
│   ├── OPERATIONS.md
│   └── ASSUMPTIONS.md
│
├── runbooks/
│   ├── upgrade_pivx.md
│   ├── rolling_restart.md
│   ├── collect_quorum_logs.md
│   └── isolate_cohort.md
│
└── scripts/
    ├── generate_stub_host_vars.py     ← already executed; generated cb2–7, ovh2–5
    ├── validate_inventory.py          ← run before every deployment
    └── show_layout.py                 ← prints host/instance/port table
```

---

## 3. Files to Review First

Priority order — start here before touching anything else.

### 3.1 `ansible/inventories/testnet6/group_vars/all/main.yml`
**Why:** Contains every global default. Nothing deploys correctly until `pivx_version`, `pivx_archive_url`, and `pivx_checksum_sha256` are real values.

Key variables to fill:
```yaml
pivx_version: "5.6.1"            # ← set; update when a testnet build is cut
pivx_checksum: "sha256:REPLACE_ME"  # ← fetch from GitHub release sha256sums.txt for v5.6.1
loki_endpoint: "http://tn6-infra01:3100"  # ← confirm infra01 IP
```

Note: Sapling parameter files (`sapling-spend.params`, `sapling-output.params`, `sprout-groth16.params`) are now downloaded automatically by the `pivx_install` role before any instance starts. No manual `sapling-fetch-params` step required.

**Your notes:**
> 

---

### 3.2 `ansible/inventories/testnet6/host_vars/tn6-cb1.yml`
**Why:** This is the canonical, fully-annotated instance schema. Every other host_vars file follows its structure. Reviewing this once gives you full understanding of the instance model.

Key schema per instance:
```yaml
- name: tn6-cb1-v4-mn01
  enabled: true
  slot: 0
  protocol_class: ipv4
  cohort: cohort_ipv4
  bind_addr: "0.0.0.0"
  external_ip: "203.0.113.1"     # ← REPLACE placeholder IPs everywhere
  p2p_port: 51474
  rpc_port: 51478
  bls_operator_key: "REPLACE_ME" # ← generate with: pivx-cli bls generate
```

**Your notes:**
> 

---

### 3.3 `ansible/inventories/testnet6/hosts.yml`
**Why:** Master inventory. Confirm every host is in the right groups (provider, protocol cohort, chaos group). All IPs are RFC 5737 placeholders.

**Your notes:**
> 

---

### 3.4 `ansible/roles/pivx_instance/templates/pivx.conf.j2`
**Why:** This template renders the per-instance `pivx.conf`. Verify the Testnet6 network flags, `addnode` seed addresses, and `masternode` section are correct for the version you're deploying.

**Your notes:**
> 

---

### 3.5 `ansible/roles/pivx_instance/templates/pivxd@.service.j2`
**Why:** Systemd unit template. Binary path is now `/opt/pivx/current/bin/pivxd` (via symlink
from `/opt/pivx/releases/<version>/`). Confirm `User=pivx` is the correct service account.

**Your notes:**
> 

---

### 3.6 `ansible/roles/vector/templates/vector.toml.j2`
**Why:** Log pipeline. Vector ships all `pivxd@*.service` journal entries to Loki with protocol/cohort/role labels baked in at deploy time. Verify the Loki endpoint and label set match what you want to query.

**Your notes:**
> 

---

### 3.7 `docs/DEPLOYMENT_PLAN.md`
**Why:** 7-phase bring-up sequence. Read this before running anything. Phase ordering matters — Tor must deploy before DMN registration, monitoring should be up before chaos testing begins.

**Your notes:**
> 

---

### 3.8 `docs/ASSUMPTIONS.md`
**Why:** Every engineering assumption made during scaffolding, with explicit risk ratings. This is the fastest way to find things that may not match your environment.

**Your notes:**
> 

---

## 4. Assumptions Made

| # | Assumption | Where it matters |
|---|---|---|
| 1 | Ubuntu 22.04 LTS / x86_64 on all hosts | `bootstrap.yml` asserts this; will fail on other OS |
| 2 | PIVX version is `5.6.99` (placeholder) | `group_vars/all/main.yml` — must replace before deploy |
| 3 | P2P port base 51474, RPC port base 51478 | Per-slot offset ×10: IPv4=+0, IPv6=+10, Tor=+20 |
| 4 | 3 instances per host (1 per protocol cohort) | All host_vars structured this way; ~36 MNs total |
| 5 | `pivx` system user owns all instance data | All dirs, units, and files set `owner: pivx` |
| 6 | Monitoring host `tn6-infra01` runs entire observability stack | Single host — no HA for monitoring in this scaffold |
| 7 | Vector instead of Promtail for log shipping | VRL transforms bake metadata at deploy time; active upstream |
| 8 | Individual systemd unit files (not `%i` substitution) | Each instance gets its own unit for full config isolation |
| 9 | All BLS operator keys are `REPLACE_ME` stubs | `validate_inventory.py` enforces these are populated before deploy |
| 10 | IPv6 dual-stack available on all hosts with a `/64` assigned | Not verified — OVH and Contabo handle this differently |
| 11 | Monitoring has no TLS / auth in this scaffold | Testnet-appropriate; add reverse proxy + certs if exposed |
| 12 | No backup strategy defined | Datadir and wallet persistence is out of scope here |

---

## 5. Blocking Items (Nothing Runs Without These)

These must be resolved before running any playbook.

### 5.1 Real IP addresses
All host_vars use RFC 5737 / RFC 3849 placeholders:
- IPv4: `203.0.113.x`
- IPv6: `2001:db8::x`

**Action:** Replace with actual VPS IPs in every `host_vars/*.yml` file.

**Status:** [ ] Not started / [ ] In progress / [ ] Done

---

### 5.2 PIVX checksum
**File:** `ansible/inventories/testnet6/group_vars/all/main.yml`

Version is set to `5.6.1`. The download URL is auto-constructed. Only the SHA-256 checksum remains:
```yaml
pivx_checksum: "sha256:REPLACE_ME"
```
Fetch it from the [v5.6.1 release page](https://github.com/PIVX-Project/PIVX/releases/tag/v5.6.1) → `sha256sums.txt` → find `pivx-5.6.1-x86_64-linux-gnu.tar.gz`.

Sapling parameter checksums are already populated from the official z.cash download server.

**Status:** [ ] Not started / [ ] In progress / [ ] Done

---

### 5.3 Vault secrets
**File:** `ansible/inventories/testnet6/group_vars/all/vault.yml.example`  
Copy to `vault.yml`, populate, then encrypt:
```bash
cp ansible/inventories/testnet6/group_vars/all/vault.yml.example \
   ansible/inventories/testnet6/group_vars/all/vault.yml
# edit vault.yml with real values
ansible-vault encrypt ansible/inventories/testnet6/group_vars/all/vault.yml
```

Secrets needed: RPC passwords per instance, Grafana admin password, Alertmanager auth, any API tokens.

**Status:** [ ] Not started / [ ] In progress / [ ] Done

---

### 5.4 BLS operator keypairs
Generate one keypair per masternode instance:
```bash
pivx-cli bls generate
```
Populate `bls_operator_key` in each instance dict across all host_vars files. 36 instances × 1 key each.

**Note:** BLS keys are generated AFTER Phase 1 deployment (need a running pivxd).  
Do NOT block Phase 1 or Phase 2 on this — fill them in before Phase 5 (masternode registration).

**Status:** [ ] Not started / [ ] In progress / [ ] Done

---

### 5.6 `mining_phase_target_height` — confirm `nFirstPoSBlock`
**File:** `ansible/inventories/testnet6/group_vars/all/main.yml`

Default value is `201`. This is the block height at which PIVX testnet activates PoS.
Verify by checking the PIVX source:
```bash
grep -r "nFirstPoSBlock\|nPosStartHeight" <pivx-src>/src/chainparams.cpp
```
Or ask the PIVX dev team for the Testnet6-specific value.

```yaml
mining_phase_target_height: 201   # ← confirm with PIVX devs
```

**Status:** [ ] Not started / [ ] In progress / [ ] Done

---

### 5.7 Bootstrap mining addresses
**Files:** `host_vars/tn6-seed01.yml`, `host_vars/tn6-seed02.yml`

For Phase 2 (bootstrap mining), each miner needs a valid testnet PIVX address
to receive mining rewards:
```yaml
bootstrap_mining_address: "REPLACE_ME"   # ← testnet address
```
Generate after Phase 1 deploy completes:
```bash
pivx-cli -conf=/etc/pivx/<instance>/pivx.conf getnewaddress
```

**Status:** [ ] Not started / [ ] In progress / [ ] Done

---

### 5.5 SSH key
`ansible.cfg` references `~/.ssh/tn6_deploy_key`. Ensure this key exists and is authorized on all hosts, or update the `private_key_file` path in `ansible.cfg`.

**Status:** [ ] Not started / [ ] In progress / [ ] Done

---

## 6. High-Risk Areas

### 6.1 No PIVX Prometheus exporter exists
**Risk: HIGH**

The alert rule `PivxdInstanceDown` in `prometheus/templates/prometheus_rules/pivx_alerts.yml.j2` is a placeholder. PIVX does not ship a native Prometheus exporter. Node health currently only comes from node_exporter (OS metrics) and log parsing via Loki.

**Options:**
- A) Write a polling exporter that wraps `pivx-cli getblockchaininfo` / `getpeerinfo` / `masternode status`
- B) Use Loki alerting rules on log patterns as a proxy
- C) Accept the gap for now and rely on systemd service state + node_exporter

**Decision:**
> 

---

### 6.2 Tor onion addresses are unknown until first deploy
**Risk: MEDIUM**

v3 onion addresses are generated by Tor on first start. The workflow is:
1. Run `deploy_tor.yml`
2. Harvest addresses from `/var/lib/tor/tn6-*-tor-*/hostname` on each host
3. Populate those addresses into the DMN registration transactions
4. Then register DMNs on-chain

The host_vars have `onion_address: ""` stubs. There is no automated harvesting playbook yet.

**Decision:**
> 

---

### 6.3 IPv6 routing on VPS
**Risk: MEDIUM**

OVH and Contabo handle IPv6 differently:
- OVH: typically requires a `/128` gateway config or `ip -6 route add` via VPS control panel
- Contabo: varies by product line; may need explicit IPv6 enable

Verify before running IPv6 cohort deployment: `ip -6 addr show` and `ping6 <external IPv6>` from each host.

**Decision:**
> 

---

### 6.4 LLMQ / quorum parameters
**Risk: MEDIUM**

`pivx.conf.j2` uses LLMQ type 1 defaults. If Testnet6 uses a different quorum size, threshold, or type identifiers, the quorum formation will fail silently (nodes will be registered but no quorum will complete DKG).

**Decision:**
> 

---

### 6.5 Monitoring host is a single point of failure
**Risk: LOW-MEDIUM** (for a testnet)

`tn6-infra01` runs Prometheus, Loki, Grafana, and Alertmanager all on one host with no replication or persistent volume strategy. If it goes down during a chaos experiment, you lose observability.

**Decision:**
> 

---

### 6.6 Alertmanager Slack webhook
**Risk: LOW**

`alertmanager.yml.j2` has `slack_api_url: "REPLACE_ME"`. Alerts will fail to route until this is set. Alternative: switch to email or disable Slack entirely.

**Decision:**
> 

---

## 7. Quick Start Sequence

**Full lifecycle quickstart is in [docs/QUICKSTART.md](docs/QUICKSTART.md).**

Short version once §5 blocking items are resolved:

```bash
# Validate and lint
make check-inventory
make lint

# Phase 1: Deploy
make bootstrap
make deploy

# Phase 2: Mine to PoS activation height
make start-bootstrap-mining
watch -n 30 make verify-readiness   # wait for READY message

# Phase 3: Transition to PoS
make transition-to-pos
# Edit group_vars/all: lifecycle_phase: staking
make deploy-pivx

# Phase 4: Enable staking (fund wallets + unlock first)
make enable-staking

# Phase 5: Register masternodes (manual ProRegTx), then:
make enable-masternodes

# Phase 6: Chaos testing
make chaos-inject-latency COHORT=tor DELAY=200ms
```

**To restart from genesis:**
```bash
make wipe-chain
# Edit group_vars/all: lifecycle_phase: bootstrap_mining
make deploy
make start-bootstrap-mining
```

---

## 8. Your Notes

Use this section freely during review.

### Open questions
> 

### Decisions made
> 

### Changes needed
> 

### Other
> 

---

*End of review document.*
