# Runbook: Collect Debug Bundle

**When to use**: When diagnosing a failing instance, quorum regression, or anomalous
chain behavior. This runbook collects logs, chain info, peer data, and service state
from one or more instances and archives them for analysis.

---

## Quick commands

```bash
# Collect debug bundle from ALL hosts
make collect-debug

# Collect from a specific host only
make collect-debug LIMIT=tn6-cb1

# Collect recent logs for a specific instance by name
scripts/collect_logs.sh tn6-cb1-tor-mn05

# Collect logs from a failing Tor instance + print quorum status
scripts/collect_logs.sh tn6-cb1-tor-mn05 --quorum
```

---

## What gets collected

The `collect_debug.yml` playbook gathers:

| Item | Source |
|------|--------|
| `getblockchaininfo` | RPC per instance |
| `getpeerinfo` | RPC per instance |
| `getmasternode list` | RPC per instance (Phase 4+) |
| `quorum list` / `quorum dkgstatus` | RPC per instance (Phase 4+) |
| `journalctl -u pivxd@<instance>` last 500 lines | systemd journal |
| `systemctl status pivxd@<instance>` | systemd |
| `ip route show` / `ss -tlnp` | local netstat |
| `/var/log/pivx/chaos.log` | chaos event log |

Output is archived to `debug-bundles/YYYYMMDD-HHMMSS/` on the Ansible control node.

---

## Procedure for a failing instance

### Step 1 — Identify the failing instance

```bash
make status
# Look for instances showing: stopped, failed, or anomalous block height
```

### Step 2 — Collect logs

```bash
# Via Ansible (structured, all data)
make collect-debug LIMIT=<hostname>

# Via script (faster, just logs for one instance)
scripts/collect_logs.sh <instance-name>
# e.g.:
scripts/collect_logs.sh tn6-cb1-tor-mn05
```

The script creates `debug-bundles/<instance-name>-<timestamp>/` locally.

### Step 3 — Inspect the journal

```bash
# Direct on the host:
ssh root@<host-ip>
journalctl -u pivxd@tn6-cb1-tor-mn05 -n 200 --no-pager

# Most useful patterns to look for:
journalctl -u pivxd@tn6-cb1-tor-mn05 --no-pager | grep -E "ERROR|WARN|Masternode|quorum|DKG"
```

### Step 4 — Check chain state

```bash
ssh root@<host-ip>
CONF=/etc/pivx/tn6-cb1-tor-mn05/pivx.conf
DATA=/var/lib/pivx/tn6-cb1-tor-mn05

# Block height and sync
pivx-cli -conf=$CONF -datadir=$DATA getblockchaininfo

# Peers
pivx-cli -conf=$CONF -datadir=$DATA getpeerinfo | jq '[.[] | {addr, subver, synced_blocks}]'

# Masternode status (Phase 4+)
pivx-cli -conf=$CONF -datadir=$DATA masternode status

# Quorum DKG status
pivx-cli -conf=$CONF -datadir=$DATA quorum dkgstatus
```

### Step 5 — Check Tor hidden service (Tor instances only)

```bash
ssh root@<host-ip>
# Verify Tor is running and hidden service is up
systemctl status tor
cat /var/lib/tor/tn6-cb1-tor-mn05/hostname
# → should show .onion address

# Check Tor logs
journalctl -u tor -n 100 --no-pager | grep -E "ERROR|WARN|Bootstrapped|circuit"
```

---

## Grafana / Loki log search

Log queries to use in Grafana → Explore → Loki:

```logql
# All logs for one instance
{job="pivxd", instance="tn6-cb1-tor-mn05"}

# ERROR and WARN lines across the fleet
{job="pivxd"} |= "ERROR"

# DKG-related events (quorum formation)
{job="pivxd"} |= "DKG"

# Mining phase events
{job="pivxd", lifecycle_phase="bootstrap_mining"}

# All logs from a specific provider
{job="pivxd", provider="contabo"}
```

---

## Sharing debug bundles with developers

The collected bundle in `debug-bundles/` can be zipped for sharing:
```bash
tar -czf debug-$(date +%Y%m%d).tar.gz debug-bundles/
```

Redact RPC passwords before sharing externally:
```bash
find debug-bundles/ -name "*.txt" -exec sed -i 's/rpcpassword=.*/rpcpassword=REDACTED/g' {} +
```
