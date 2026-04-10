# Runbook: Rolling Restart

## When to use this

- Config change requires a restart of all masternode instances
- Validating that rolling restarts do not disrupt quorum
- Before chaos testing to ensure clean baseline

---

## Run

```bash
make rolling-restart
```

Restarts 3 hosts at a time (approximately 25% of masternodes per batch).
Pauses 30 seconds between batches to allow re-sync.

---

## Monitor during restart

```bash
# Watch quorum list on observer
watch -n 10 'pivx-cli -conf=/etc/pivx/tn6-obs01/pivx.conf \
             -datadir=/var/lib/pivx/tn6-obs01 \
             quorum list | jq ".llmq_50_60 | length"'
```

In Loki:
```logql
{job="pivxd"} |= "started" | __error__=""
```

---

## Manual single-host restart

```bash
ansible-playbook -i ansible/inventories/testnet6 \
  ansible/playbooks/chaos/rolling_restart.yml \
  --limit tn6-cb1
```

---

## Manual single-instance restart

```bash
ssh deploy@<host>
sudo systemctl restart pivxd@<instance>.service
sudo systemctl status  pivxd@<instance>.service
