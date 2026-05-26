# Architecture — PIVX Testnet6 Quorum Lab

## Purpose

This environment exists to test PIVX v6.0-era staking, deterministic
masternodes, and LLMQ quorum behavior under controlled failure scenarios. It is
not a public testnet; it is an instrumented lab for repeatable network creation,
startup, shutdown, cohort isolation, and evidence collection.

The primary research question is:

> Does the network continue to form and maintain quorums when protocol cohorts,
> provider groups, or selected host subsets are degraded or unavailable?

---

## Active Fleet

The active funded topology is Contabo-only:

| Count | Host range | Plan class | Role |
|-------|------------|------------|------|
| 7     | `tn6-cb1..tn6-cb7` | Contabo 4 vCPU | Masternode hosts |
| 8     | `tn6-cb8..tn6-cb15` | Contabo 6 vCPU | Masternode hosts |
| 3     | `tn6-cb1..tn6-cb3` | colocated | Seeder/bootstrap-miner instances |
| 1     | `tn6-infra01` | ops | Observer + monitoring |

OVH/Kimsufi KS-A is planned as a later expansion. The target is 10-12 hosts at
first, ideally 15 when budget allows. Until then, `provider_ovh` is present but
empty in the active inventory.

---

## Per-Host Composition

Each masternode host runs six PIVX masternode instances:

| Slot | Protocol | Cohort | P2P | RPC |
|------|----------|--------|-----|-----|
| 0 | IPv4 | `ipv4` | 51474 | 51478 |
| 1 | IPv4 | `ipv4` | 51484 | 51488 |
| 2 | IPv6 | `ipv6` | 51494 | 51498 |
| 3 | IPv6 | `ipv6` | 51504 | 51508 |
| 4 | Tor | `tor` | 51514 | 51518 |
| 5 | Tor | `tor` | 51524 | 51528 |

`tn6-cb1`, `tn6-cb2`, and `tn6-cb3` also run one colocated seeder/bootstrap
instance:

| Slot | Role | P2P | RPC |
|------|------|-----|-----|
| 6 | seeder/bootstrap-miner | 51534 | 51538 |

This yields 90 masternode instances in the active Contabo fleet: 30 IPv4, 30
IPv6, and 30 Tor, plus three startup seeders.

---

## Observer Node

`tn6-infra01` runs a non-masternode PIVX observer instance with `txindex=1`.
It also hosts Prometheus, Loki, Grafana, and Alertmanager.

The observer is the default RPC target for status checks and debugging, while
the monitoring stack provides fleet-level metrics and log queries.

---

## Seed Nodes

The startup seeders are colocated on the first three Contabo masternode hosts:

- `tn6-cb1-seed01`
- `tn6-cb2-seed02`
- `tn6-cb3-seed03`

During bootstrap mining, these instances mine the initial PoW blocks. After the
network transitions to PoS, they remain high-connection seed peers. The hosts
also continue to run their normal masternode instances.

---

## Why Mixed Protocol Composition Per Host

Each host carries every protocol cohort. This keeps provider or host failures
from being confused with protocol failures. If a provider group is stopped, it
removes roughly equal fractions of IPv4, IPv6, and Tor masternodes. If a cohort
is stopped, Ansible filters by per-instance `cohort` and leaves the other local
instances running.

This model trades some per-instance isolation for a much larger quorum lab at a
reasonable VPS count.

---

## Systemd Instance Management

PIVX instances use one systemd service per instance:

```text
pivxd@<instance>.service
```

Each instance has its own:

- `/etc/pivx/<instance>/pivx.conf`
- `/etc/pivx/<instance>/instance.env`
- `/var/lib/pivx/<instance>/`
- `/var/log/pivx/<instance>/debug.log`

RPC binds only to `127.0.0.1`.

---

## Chaos Model

The repo supports:

- Cohort stop/start/restart by `cohort: ipv4|ipv6|tor`
- Provider stop/start by `provider_contabo` and, later, `provider_ovh`
- Rolling restarts
- Host-level `tc/netem` latency and packet-loss injection
- Debug bundle collection after experiments

Important: `tc/netem` is host-interface scoped. On mixed-protocol hosts it
affects all traffic on the selected hosts, not only one PIVX process. Use
cohort stop/start for precise protocol-cohort removal.

---

## Observability Stack

| Component | Role |
|-----------|------|
| Prometheus | Metrics collection |
| node_exporter | Host OS metrics |
| process-exporter | Process-level pivxd/tor/vector visibility |
| Loki | Log aggregation |
| Vector | Journald log shipper on every host |
| Grafana | Dashboards and Explore |
| Alertmanager | Alert routing |

All logs are labeled with host, provider, role, instance, protocol class,
cohort, chain, and lifecycle phase.

---

## Security Assumptions

- SSH key-based auth only
- `deploy` user has sudo for Ansible
- `pivx` user owns daemon data and services
- PIVX RPC stays localhost-only
- Real secrets live in Ansible Vault, not git
- Monitoring should be protected by firewall, tunnel, VPN, or reverse proxy
