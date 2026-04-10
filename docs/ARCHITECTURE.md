# Architecture — PIVX Testnet6 Quorum Lab

## Purpose

This environment exists to test **LLMQ quorum formation and resilience** as
implemented in PIVX v6.0. It is not a public testnet; it is a controlled,
instrumented lab for the core team.

The primary research question is:

> Does the quorum formation algorithm behave correctly — and does the network
> remain functional — when up to one full protocol cohort or one provider subset
> is unavailable?

---

## Fleet Design

### 15-Host Fleet

| Count | Role       | Provider mix |
|-------|------------|--------------|
| 7     | Masternode | Contabo      |
| 5     | Masternode | OVH          |
| 1     | Seeder     | Contabo      |
| 1     | Seeder     | OVH          |
| 1     | Infra/Obs  | Contabo      |

### Per-Host Composition

Each of the 12 masternode hosts runs **3 PIVX instances**:

| Slot | Protocol | Cohort |
|------|----------|--------|
| 0    | IPv4     | ipv4   |
| 1    | IPv6     | ipv6   |
| 2    | Tor      | tor    |

This means 36 masternode instances across 12 hosts, plus 9 additional
instances for the remaining masternode hosts = **45 total masternode instances**.

Every individual host becomes a microcosm of the full protocol mix. This is a
deliberate choice — see *Why Mixed Composition* below.

### Observer Node

`tn6-infra01` runs a non-masternode PIVX instance with `txindex=1` for full
transaction lookups. This is the RPC target for debugging and log collection.
It also hosts the monitoring stack (Prometheus, Loki, Grafana, Alertmanager).

### Seed Nodes

`tn6-seed01` (Contabo) and `tn6-seed02` (OVH) are the initial network bootstrap
targets. Both seed nodes are **not** masternodes. They are listed as `addnode=`
entries in all PIVX configs.

Having seed nodes on two different providers guards against a single-provider
outage making it impossible to bootstrap new or restarting nodes.

---

## Why Mixed Protocol Composition Per Host

### What we chose

Each masternode host runs one instance of every protocol (IPv4, IPv6, Tor).

### What we rejected

- *Protocol-only hosts*: assigning e.g. all Contabo hosts to IPv4 and all OVH
  hosts to IPv6. This would make a provider outage indistinguishable from a
  protocol cohort outage. The tests would conflate two failure modes.

- *Single-instance hosts*: cleaner isolation but far more hosts needed for the
  same quorum coverage.

### Why mixed is right

1. **Decoupling provider from protocol**: stopping the full Contabo provider
   removes 7/15 hosts but preserves roughly equal fractions of each
   protocol cohort. The experiment remains clean.
2. **More realistic**: production masternodes will be geographically and
   operationally diverse even within a single protocol class.
3. **Fewer hosts needed**: 12 hosts × 3 instances = 36 instances across all
   three cohorts, without needing 36 separate VPS.

---

## Naming Convention

```
tn6-<provider><id>-<proto>-<role><nn>
```

| Segment      | Values                        |
|--------------|-------------------------------|
| `tn6`        | testnet6 constant prefix      |
| `cb` / `ovh` | Contabo / OVH provider        |
| `<id>`       | numeric host sequence         |
| `v4` / `v6` / `tor` | protocol class         |
| `mn`         | role (masternode)             |
| `<nn>`       | global sequence number        |

**Examples:**
- `tn6-cb1-v4-mn01` — Contabo host 1, IPv4 protocol, first masternode instance
- `tn6-ovh3-tor-mn30` — OVH host 3, Tor protocol, instance number 30
- `tn6-seed01` — first seed node (Contabo)
- `tn6-obs01` — observer node (on infra01)

---

## Port Allocation Strategy

Each host runs 3 PIVX instances. Ports are offset by slot × 10:

| Slot | Protocol | P2P Port | RPC Port |
|------|----------|----------|----------|
| 0    | IPv4     | 51474    | 51478    |
| 1    | IPv6     | 51484    | 51488    |
| 2    | Tor      | 51494    | 51498    |

Port offsets are applied from the base values (`pivx_p2p_port_base`,
`pivx_rpc_port_base`) defined in `group_vars/all/main.yml`.

All RPC listeners bind to `127.0.0.1` only — no remote RPC access.

---

## Systemd Instance Management

PIVX instances use the systemd template unit pattern: `pivxd@<instance>.service`

Each instance has its own:
- `/etc/pivx/<instance>/pivx.conf` — full config
- `/etc/pivx/<instance>/instance.env` — metadata env vars for Vector
- `/var/lib/pivx/<instance>/` — blockchain data
- `/var/log/pivx/<instance>/debug.log` — PIVX debug log
- `/etc/systemd/system/pivxd@<instance>.service` — dedicated unit file

This means systemd instance templating is superseded per-instance: each service
file is written individually (not using `%i` substitution) to allow fully
distinct configs per instance.

---

## Protocol Cohort Design

### Three Cohorts

| Cohort | Instances | Purpose |
|--------|-----------|---------|
| `ipv4` | 12 (mn) + 2 (seed) | Baseline / most widely supported |
| `ipv6` | 12 (mn)            | IPv6-only network path testing |
| `tor`  | 12 (mn)            | Tor hidden service testing, privacy |

### Cohort Isolation Tests

- **Stop a cohort**: systemd stop on all instances with matching `cohort=` label
- **Apply netem to a cohort**: all hosts in that cohort group get tc/netem rules
- **Partial stop**: stop a provider subset of a cohort (e.g., Contabo IPv6 only)

Cohort groups in Ansible are at the *host* level because netem operates on
network interfaces, not individual processes. Instance-level cohort logic is
implemented in playbook task filters (`selectattr('cohort', 'equalto', target)`).

---

## Observability Stack

See [OBSERVABILITY.md](OBSERVABILITY.md) for full detail.

| Component    | Role |
|--------------|------|
| Prometheus   | Metrics collection (node_exporter scraped from all hosts) |
| Grafana      | Dashboards, alert UI |
| Loki         | Log aggregation |
| Vector       | Log ship agent on every host |
| Alertmanager | Alert routing (Slack) |

All labels carry: `host`, `instance`, `provider`, `chain`, `cohort`,
`protocol_class`, `role`. This allows log/metric queries to be directly
correlated with quorum membership.

---

## Security Assumptions

- SSH key-based auth only; password auth disabled
- `deploy` user with sudo for Ansible ops; `pivx` user for services
- No remote RPC access; all RPC is localhost-only
- Tor instances bind P2P on localhost, hidden service address resolves outside
- Grafana/Prometheus/Loki exposed only on localhost or restricted CIDR
- No private keys, collateral txids, or real IPs committed to git
