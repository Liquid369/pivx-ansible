# Operations Guide — Day-2 Procedures

## Common Tasks

### Show instance status across the fleet

```bash
make status
```

### Check one instance manually

```bash
pivx-cli \
  -conf=/etc/pivx/<instance>/pivx.conf \
  -datadir=/var/lib/pivx/<instance> \
  getblockchaininfo
```

---

## Binary Upgrade

See [runbooks/upgrade_pivx.md](../runbooks/upgrade_pivx.md).

Quick reference:
1. Update `pivx_version` and `pivx_checksum` in `group_vars/all/main.yml`
2. `make upgrade-pivx`

Upgrade rolls 3 hosts at a time. The old binary symlinks are overwritten.
Previous versions remain in `/opt/pivx/<version>/` until cleaned manually.

---

## Rolling Restart

No binary change; just restart all masternode instances in rolling order:

```bash
make rolling-restart
```

---

## Cohort Operations

```bash
# Stop entire cohort
make cohort-stop COHORT=tor

# Start it again
make cohort-start COHORT=tor

# Restart cohort
make cohort-restart COHORT=ipv6
```

---

## Adding a New Host

1. Provision the VPS with Ubuntu 22.04 and `deploy` user access.
2. Add to `ansible/inventories/testnet6/hosts.yml` in the appropriate groups.
3. Create `host_vars/<hostname>.yml` (copy from `tn6-cb1.yml` and edit).
4. Assign unique instance names and sequence numbers.
5. Run `make check-inventory` to validate.
6. Run `make bootstrap --limit <hostname>`.
7. Run `make deploy-tor --limit <hostname>` if it has Tor instances.
8. Register DMNs externally.
9. Run `make deploy-pivx --limit <hostname>`.

---

## Removing a Host or Instance

### Disable an instance without removing it

1. Set `enabled: false` on the instance in host_vars.
2. `make deploy-pivx --limit <hostname>` — Ansible will stop the service.

### Full removal

1. SSH to the host: stop the service, remove systemd unit, remove directories.
2. Remove from `hosts.yml` and delete `host_vars/<hostname>.yml`.
3. Update `make check-inventory` to confirm clean.

---

## Collecting Logs for a Quorum Failure

1. Note the approximate time window.
2. Run `make chaos-collect-debug` (collects current state + last 500 log lines).
3. In Grafana Loki (Explore):
   ```logql
   {job="pivxd"} |= "llmq" | __error__=""
   ```
4. Look for DKG errors:
   ```logql
   {job="pivxd"} |~ "(?i)(dkg|quorum).*(fail|error|timeout)"
   ```
5. Cross-reference with node metrics (peer count, CPU, disk) in the same
   time window in Grafana.

See also: [runbooks/collect_quorum_logs.md](../runbooks/collect_quorum_logs.md)

---

## Firewall Management

UFW is managed by Ansible. To open an additional port:

```bash
ansible -i ansible/inventories/testnet6 <host> -m community.general.ufw \
  -a "rule=allow port=<port> proto=tcp" --become
```

---

## Log Locations

| Path | Contents |
|------|----------|
| `/var/log/pivx/<instance>/debug.log` | PIVX instance debug log |
| `/var/log/pivx/chaos.log` | Chaos event log (written by Ansible playbooks) |
| `/var/log/pivx/upgrade.log` | Upgrade event log |
| journald `pivxd-<instance>` | Same as debug.log but structured |

---

## Monitoring Access

Grafana: `http://<tn6-infra01-ip>:3000`
Prometheus: `http://<tn6-infra01-ip>:9090`
Loki (raw API): `http://<tn6-infra01-ip>:3100`
Alertmanager: `http://<tn6-infra01-ip>:9093`

Access restricted by UFW. Open to your operator IP as needed:
```bash
ufw allow from <your-ip> to any port 3000,9090,3100,9093 proto tcp
```
