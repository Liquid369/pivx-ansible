# testnet6-ansible

Ansible-managed deployment scaffold for the **PIVX Testnet6 quorum testing environment**.

This repository provisions and operates the active 15-server Contabo Testnet6
fleet, with mixed IPv4, IPv6, and Tor masternode cohorts plus three colocated
seed/bootstrap-miner instances for network startup.

---

## Purpose

PIVX v6.0 introduces deterministic masternodes (DMNs) and LLMQ-based quorum selection.
This lab exists to:

- Test quorum formation across mixed protocol cohorts
- Validate continued operation when a cohort or provider subset fails
- Simulate network faults (latency, packet loss, partition) with controlled chaos scenarios
- Gather structured logs and metrics that explain quorum failures for bug triage

This is **not** a public testnet. It is a controlled quorum testing lab with deliberate
failure injection capability.

---

## Repository Layout

```
testnet6-ansible/
├── ansible.cfg                  # Ansible runtime config
├── Makefile                     # Task runner / common operation shortcuts
├── ansible/
│   ├── inventories/testnet6/    # Hosts, group_vars, host_vars
│   ├── roles/                   # All Ansible roles
│   ├── playbooks/               # Top-level playbooks
│   └── files/                   # Static files deployed by roles
├── docs/                        # Architecture, design, and ops docs
├── monitoring/                  # Raw config for Prometheus/Loki/Grafana/Alertmanager
├── runbooks/                    # Step-by-step operational procedures
├── scripts/                     # Inventory validation and helper scripts
└── templates/                   # Shared Jinja2 templates (PIVX conf, systemd units)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design.

---

## Host Fleet Summary

| Alias range     | Provider | Plan class | Role(s) |
|-----------------|----------|------------|---------|
| tn6-cb1..cb3    | Contabo  | 4 vCPU     | 6 masternodes + 1 seeder/bootstrap-miner each |
| tn6-cb4..cb7    | Contabo  | 4 vCPU     | 6 masternodes each |
| tn6-cb8..cb15   | Contabo  | 6 vCPU     | 6 masternodes each |
| tn6-infra01     | Contabo  | small/ops  | observer + monitoring |

Active fleet totals:

- 15 Contabo masternode servers: 7 smaller 4 vCPU nodes and 8 larger 6 vCPU nodes
- 90 masternode instances: 30 IPv4, 30 IPv6, 30 Tor
- 3 colocated seeder/bootstrap-miner instances on `tn6-cb1..tn6-cb3`
- 1 observer instance on `tn6-infra01`

OVH/Kimsufi KS-A is documented as a future expansion target. The active
`provider_ovh` inventory group is intentionally empty until those servers are
purchased.

---

## Quick Start

### Prerequisites

- Ansible >= 2.14
- Python 3.9+
- SSH access to all target hosts
- `vault_pass.txt` populated (see [docs/DEPLOYMENT_PLAN.md](docs/DEPLOYMENT_PLAN.md))

```bash
pip install -r requirements.txt
cp ansible/inventories/testnet6/group_vars/all/vault.yml.example \
   ansible/inventories/testnet6/group_vars/all/vault.yml
# edit vault.yml then:
ansible-vault encrypt ansible/inventories/testnet6/group_vars/all/vault.yml
```

### Testnet Lifecycle — run in this order for a fresh chain

```bash
# Phase 0-1: OS prep + seed mesh/full deployment
make bootstrap                          # OS packages, pivx user, firewall rules
make deploy                             # PIVX binary, seeders, MN configs, Tor, monitoring
make status                             # confirm seeders and peers are reachable

# Phase 2: Bootstrap mining (PoW blocks + initial test coins)
make start-bootstrap-mining             # mine on cb1/cb2/cb3 seeder wallets
make verify-readiness                   # poll fleet until height >= 201 (nFirstPoSBlock)

# Phase 3: Transition to Proof-of-Stake and fund staking wallets
make transition-to-pos                  # stops mining, regenerates pivx.conf with gen=0
# Edit group_vars/all/main.yml: lifecycle_phase: staking
make deploy-pivx                        # push updated configs to all instances
make enable-staking                     # verify staking wallets and activation

# Phase 4: Stake until funds mature, then register masternodes
# (generate BLS keys, fund collateral, broadcast ProRegTx — all done externally)
# Edit host_vars/<host>.yml: bls_operator_key, masternode_enabled: true
# Edit group_vars/all/main.yml: lifecycle_phase: masternode_quorum
make deploy-pivx                        # push masternode configs
make enable-masternodes                 # verify DMN status and quorum list

# Phase 5: Upgrade/migrate to v6.0 feature-test binaries when ready
make upgrade-pivx PIVX_VERSION=6.0.0-test
make verify-readiness

# Phase 6: Chaos testing
make chaos-inject-latency COHORT=tor DELAY=200ms JITTER=20ms
make chaos-inject-loss COHORT=ipv6 LOSS=10
make cohort-stop COHORT=ipv4
make collect-debug                      # collect logs + chain state from fleet

# Reset: wipe chain and start over
make wipe-chain                         # preserves wallets by default
```

### Protocol cohort operations

```bash
make cohort-stop COHORT=tor
make cohort-start COHORT=ipv6
make cohort-restart COHORT=ipv4
make cohort-stop COHORT=ipv6            # stop all IPv6 masternodes
```

### Fault injection / chaos

```bash
make chaos-inject-latency COHORT=tor DELAY=200ms JITTER=20ms
make chaos-inject-latency COHORT=ipv6 DELAY=300ms
make chaos-inject-loss COHORT=tor LOSS=15
make chaos-clear COHORT=tor             # remove all netem rules from a cohort
make chaos-clear COHORT=ipv6
make collect-debug                      # gather debug bundle from all hosts
make collect-debug LIMIT=tn6-cb1        # one host only
```

### Day-2 ops

```bash
make rolling-restart                    # rolling restart, 1 host at a time
make upgrade-pivx PIVX_VERSION=5.7.0   # rolling binary upgrade
make status                             # quick fleet status
make verify-readiness                   # detailed phase readiness poll
```

---

## Key Docs

| Doc | Purpose |
|-----|---------|
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | **Start here** — end-to-end operator guide |
| [docs/LIFECYCLE.md](docs/LIFECYCLE.md) | Full lifecycle phase reference |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Full system design and rationale |
| [docs/INVENTORY_MODEL.md](docs/INVENTORY_MODEL.md) | Host/instance schema reference |
| [docs/DEPLOYMENT_PLAN.md](docs/DEPLOYMENT_PLAN.md) | Step-by-step bring-up |
| [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) | Metrics, logs, dashboards |
| [docs/CHAOS_TESTING.md](docs/CHAOS_TESTING.md) | Failure scenarios and procedures |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Day-2 operational tasks |
| [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) | Engineering assumptions |
| [runbooks/MIGRATE_TO_V6_FEATURES.md](runbooks/MIGRATE_TO_V6_FEATURES.md) | Upgrade path from stable chain to v6 feature tests |
| [REVIEW.md](REVIEW.md) | Blocking items + operator checklist |

---

## Important Notes

- **No real secrets, keys, or IPs are committed.** All sensitive values use placeholder
  patterns like `REPLACE_ME` or Ansible Vault references.
- **This repo assumes Ubuntu 22.04 LTS** on all nodes. See [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md).
- PIVX binaries are fetched from the official PIVX GitHub releases. No pre-built binaries
  are stored in this repository.
- Masternode collateral and operator keys must be generated externally and injected via
  host_vars before deployment.
