# Runbook: Collect Logs for a Quorum Event

## When to use this

- A quorum-related anomaly or failure is suspected
- DKG did not complete successfully
- Masternode dropped out of quorum unexpectedly
- You need to correlate logs with block height / chain events

---

## Quick automated collection

```bash
make chaos-collect-debug
```

Bundles land in `debug_bundles/<timestamp>/` on your control machine.
Each host produces a `.tar.gz` with per-instance RPC state and log tails.

---

## Manual targeted collection

### Which instances are in DKG trouble?

On the observer (tn6-infra01):
```bash
pivx-cli -conf=/etc/pivx/tn6-obs01/pivx.conf \
         -datadir=/var/lib/pivx/tn6-obs01 \
         quorum dkgstatus | jq .
```

### Tail live logs on a specific instance

```bash
ssh deploy@<host>
journalctl -u pivxd@<instance>.service -f
# Or filter for LLMQ:
journalctl -u pivxd@<instance>.service -f | grep -i "llmq\|quorum\|dkg"
```

### Pull logs for a time window via Loki (Grafana Explore)

```logql
{job="pivxd"} |= "llmq" | __error__=""
  | __time__ >= "2026-04-08T10:00:00Z"
  | __time__ <= "2026-04-08T11:00:00Z"
```

Filter by cohort:
```logql
{job="pivxd", cohort="tor"} |~ "(?i)(dkg|quorum|signing)"
```

DKG errors only:
```logql
{job="pivxd"} |~ "(?i)dkg.*(fail|error|timeout|abort)"
```

Peer disconnection events:
```logql
{job="pivxd"} |= "disconnected" |= "masternode"
```

### Correlate with host metrics

In Grafana:
1. Open the time range around the quorum event
2. Check "Fleet Overview" — look for CPU spikes, memory pressure, or node drops
3. Use the `provider` variable to filter by Contabo vs OVH hosts

---

## What to include in a bug report

1. The output of `quorum dkgstatus` from the observer
2. The output of `quorum list` showing which DMNs are active
3. The relevant log lines from at least 3 different instances across cohorts
4. The netem/tc state at the time (`tc_qdisc.txt` from debug bundle)
5. Block heights across affected instances (how far behind were struggling nodes?)
6. The chaos.log entries if a chaos action was running (`cat /var/log/pivx/chaos.log`)
7. The time window as an ISO8601 range

---

## Known log categories for LLMQ debugging

Add these to `pivx.conf` to increase verbosity (already set in defaults):
```
debug=masternode
debug=llmq
debug=mnauth
debug=net
```

Additional categories available (set in `extra_conf` for targeted instances):
- `debug=chainlocks`
- `debug=gobject`
- `debug=instantsend`
