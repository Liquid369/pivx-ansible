# Observability Design — PIVX Testnet6

## Overview

The observability stack provides **metrics** (Prometheus + node_exporter),
**logs** (Vector → Loki), and **dashboards/alerts** (Grafana + Alertmanager).

The goal is not just to know *that* something failed, but to have enough
structured data to explain *why* a quorum event happened or didn't happen.

---

## Stack Components

| Component      | Version  | Role |
|----------------|----------|------|
| Prometheus     | 2.50+    | Metrics DB + scraping |
| node_exporter  | 1.7+     | Host-level OS metrics |
| Vector         | 0.37+    | Log shipper on every node |
| Loki           | 2.9+     | Log aggregation backend |
| Grafana        | 10+      | Dashboards, Explore, alerts |
| Alertmanager   | 0.27+    | Alert routing (Slack) |

Everything runs on `tn6-infra01`. All fleet hosts run `node_exporter` and
`vector`.

---

## Why Vector, Not Promtail

| Factor          | Vector                          | Promtail |
|-----------------|---------------------------------|--------|
| Journald source | Native, no extra deps           | Supported but less flexible |
| Transform logic | VRL — full scripting per-stream | Limited pipeline |
| Multi-output    | Yes (Loki + S3 + file etc.)    | Loki-only practically |
| Memory usage    | Good; configurable              | Light but less tunable |
| Maintenance     | Active upstream (Datadog/Vector)| Grafana-managed |

Vector was chosen because VRL transforms allow us to **bake per-instance
metadata into logs at ship time**, rather than relying on Loki push labels
alone. This ensures every log line is richly labeled without requiring
Loki regex-extracted labels.

---

## Label Schema

Every metric and log line carries these labels:

| Label           | Source      | Values |
|-----------------|-------------|--------|
| `host`          | host_vars   | `tn6-cb1`, `tn6-cb15`, … |
| `instance`      | instance.name | `tn6-cb1-v4-mn01`, … |
| `provider`      | host_vars   | `contabo`, `ovh` |
| `chain`         | group_vars  | `testnet6` |
| `cohort`        | instance    | `ipv4`, `ipv6`, `tor` |
| `protocol_class`| instance    | `ipv4`, `ipv6`, `tor` |
| `role`          | instance    | `masternode`, `seeder`, `observer` |
| `node_role`     | group_vars  | `masternode`, `seeder`, `observer` |
| `job`           | scrape config | `node_exporter`, `pivxd` |

This set allows any combination of grouping/filtering:
- "Show all Tor instances" → `{cohort="tor"}`
- "Show Contabo IPv6" → `{provider="contabo", cohort="ipv6"}`
- "Show all masternodes" → `{role="masternode"}`

---

## Log Collection

Vector runs on each fleet host and scrapes:

1. **systemd journald** for all `pivxd@*.service` units
2. **systemd journald** for system-level events (SSH, networkd)

The Vector transform enriches each log entry with instance metadata baked at
deploy time (from `pivx_instances` in host_vars). No runtime string matching.

### Systemd identifier

Each PIVX service sets:
```ini
SyslogIdentifier=pivxd-<instance.name>
```

Vector strips the `pivxd-` prefix to get the bare instance name, then does a
VRL dict lookup to add protocol_class, cohort, and role.

---

## Log Query Examples (Loki / Grafana Explore)

All logs from the Tor cohort:
```logql
{job="pivxd", cohort="tor"}
```

LLMQ-related lines from all hosts:
```logql
{job="pivxd"} |= "llmq"
```

DKG errors on Contabo hosts only:
```logql
{job="pivxd", provider="contabo"} |~ "(?i)dkg.*error|error.*dkg"
```

All peer connection events on tn6-cb1:
```logql
{job="pivxd", host="tn6-cb1"} |= "connection"
```

Quorum signing events across all instances:
```logql
{job="pivxd"} |= "CLLMQUtils::IsQuorumActive"
```

Chaos event log (tracks when ops ran chaos actions):
```logql
{job="system", host=~"tn6-.*"} |= "CHAOS"
```

---

## Metrics

### Available metrics (node_exporter)

All standard node_exporter metrics are available. Particularly useful:

- `node_cpu_seconds_total` — per-host CPU breakdown
- `node_memory_MemAvailable_bytes` — memory pressure
- `node_filesystem_avail_bytes` — disk headroom
- `node_network_receive_bytes_total` / `_transmit_bytes_total` — traffic
- `node_netstat_Tcp_CurrEstab` — open TCP connections

### Process metrics and future PIVX RPC exporter

`process-exporter` is deployed to expose process-level visibility for `pivxd`,
Tor, Vector, and node_exporter.

A PIVX-specific RPC exporter should still be added to expose:
- Block height per instance
- Peer count per instance
- Quorum membership status
- DKG round state

This is listed in `ASSUMPTIONS.md` as a pending item.

---

## Alerting

Alerts fire to Slack via Alertmanager. Two channels:
- `#tn6-alerts` — all alerts
- `#tn6-critical` — critical severity only

Key alert rules (see `ansible/roles/prometheus/templates/prometheus_rules/`):

| Alert                        | Condition | Severity |
|------------------------------|-----------|----------|
| `NodeDown`                   | node_exporter unreachable 2m | critical |
| `HighCPU`                    | CPU > 90% for 10m | warning |
| `DiskSpaceLow`               | root fs < 15% | warning |
| `PivxdInstanceDown`          | PIVX exporter unreachable 3m | critical |
| `AllTorInstancesDown`        | Entire Tor cohort gone | critical |
| `AllIPv6InstancesDown`       | Entire IPv6 cohort gone | critical |
| `ProviderContaboMajorityDown`| >50% Contabo instances gone | critical |

---

## Grafana Dashboards

Dashboards are provisioned automatically from JSON files in
`ansible/roles/grafana/files/grafana_dashboards/`.

| Dashboard            | UID                  | Description |
|----------------------|----------------------|-------------|
| Fleet Overview       | `tn6-fleet-overview` | CPU, memory, uptime per host |

**Planned dashboards** (JSON stubs to be completed):
- `tn6-quorum-status` — per-cohort instance state, DKG round counters
- `tn6-network-io` — per-host, per-cohort network I/O
- `tn6-chaos-timeline` — overlay of chaos events with metrics

To add a dashboard: create/export JSON from Grafana, save to
`ansible/roles/grafana/files/grafana_dashboards/<name>.json`, run
`make deploy-monitoring --limit tn6-infra01`.

---

## Retention

| Store      | Retention |
|------------|-----------|
| Prometheus | 30 days   |
| Loki       | 30 days   |

Adjust via `prometheus_retention_time` and `loki_retention_period` in
`group_vars/monitoring.yml`.
