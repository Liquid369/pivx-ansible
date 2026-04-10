# Runbook: Isolate a Protocol Cohort

## When to use this

- Running a planned fault-injection test against a single cohort
- A cohort is causing unexpected network noise and needs isolation
- Testing recovery behavior after cohort recovery

---

## Stop a cohort

```bash
make cohort-stop COHORT=<ipv4|ipv6|tor>
```

All instances with `cohort: <value>` across all masternode and seeder hosts
will be stopped via `systemctl stop pivxd@<instance>.service`.

Verify:
```bash
make status
# Should show stopped status for the target cohort instances
```

---

## Inject network fault into a cohort

This affects all traffic on the host's primary interface, not just PIVX:

```bash
# 200ms added latency
make chaos-inject-latency COHORT=ipv6 DELAY=200ms

# 15% packet loss
make chaos-inject-loss COHORT=tor LOSS=15
```

Verify with:
```bash
ssh deploy@<host> tc qdisc show dev eth0
```

---

## Clear netem rules

```bash
make chaos-clear COHORT=<cohort>
```

---

## Restore a cohort

```bash
make cohort-start COHORT=<ipv4|ipv6|tor>
```

---

## What to observe during isolation

Before stopping:
1. Run `make chaos-collect-debug` to capture baseline state
2. Note current quorum list and block heights

During isolation:
- Watch Grafana — node_exporter will show the affected hosts still up
  (OS is fine; only PIVX processes are stopped)
- Watch Loki for remaining instances: do peer counts drop? DKG errors appear?

After restore:
1. Wait for instances to re-sync
2. Run `make chaos-collect-debug` for post-restore state
3. Compare quorum list before and after

---

## Partial cohort isolation (provider subset)

To stop only Contabo's IPv6 instances (not OVH's):

```bash
ansible-playbook -i ansible/inventories/testnet6 \
  ansible/playbooks/chaos/stop_cohort.yml \
  --limit provider_contabo \
  -e "target_cohort=ipv6"
```
