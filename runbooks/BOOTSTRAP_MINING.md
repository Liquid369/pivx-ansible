# Runbook: Bootstrap Mining (Phase 2)

**When to use**: After initial deployment (`make deploy`) succeeds and the chain
is at height 0. You need to mine at least 201 blocks so that PoS becomes valid.

**Time estimate**: 30–90 minutes (1 CPU thread). Increase `bootstrap_mining_threads`
to speed up.

---

## Background

PIVX testnet uses a hybrid PoW/PoS model. Before block `UPGRADE_POS activation height` (~201
on testnet), only PoW blocks are valid. Three colocated seed instances
(`tn6-cb1-seed01`, `tn6-cb2-seed02`, and `tn6-cb3-seed03`) act as CPU miners
during this phase via `setgenerate true <threads>`.

Mining is controlled at two levels:
1. **pivx.conf** — `gen=1` + `genproclimit=N` persists across restarts
2. **RPC runtime** — `setgenerate true/false` toggles mining without restart

The `make start-bootstrap-mining` playbook sets both.

---

## Prerequisites

- [ ] Phase 1 deployment complete (`make deploy` succeeded on all hosts)
- [ ] `make status` shows all instances running at height 0
- [ ] `host_vars/tn6-cb1.yml`, `tn6-cb2.yml`, and `tn6-cb3.yml`:
  - `mining_enabled: true`
- [ ] `group_vars/all/main.yml`: `lifecycle_phase: bootstrap_mining`

> Mining rewards are paid to each miner instance's own wallet automatically
> (`setgenerate` is a wallet RPC; this build has no `miningaddress` option).
> After the PoW phase, sweep the seeder wallets to fund staking/collateral.

---

## Procedure

### Step 1 — Push updated pivx.conf to mining nodes

```bash
make deploy-pivx
```

This pushes `gen=1` and `genproclimit=1` to cb1/cb2/cb3 seeders (because
`lifecycle_phase=bootstrap_mining` and `mining_enabled=true` on their instances).
All other instances get `gen=0`.

### Step 2 — Start runtime mining

```bash
make start-bootstrap-mining
```

This runs `setgenerate true 1` via RPC on all mining instances.
Expected output per instance:
```
TASK [pivx_bootstrap_miner : Start CPU mining] ***
ok: [tn6-cb1] => {"changed": false, "rc": 0, ...}
```

### Step 3 — Verify mining is active

```bash
# On the first seeder host:
ssh root@<tn6-cb1-ip>
pivx-cli -conf=/etc/pivx/<instance>/pivx.conf getmininginfo
```
Expected:
```json
{
  "blocks": 1,
  "currentblocksize": 1000,
  "difficulty": 0.0001,
  "hashespersec": 12345,
  "generate": true,
  "genproclimit": 1,
  ...
}
```

### Step 4 — Monitor height

```bash
make verify-readiness
```

Run this periodically. When height ≥ `mining_phase_target_height` (201):
```
STATUS: READY to transition to PoS — run: make transition-to-pos
```

### Step 5 — (Optional) Stop mining early

If you need to pause mining without transitioning to PoS:
```bash
make stop-bootstrap-mining
```

This calls `setgenerate false` via RPC. Mining config in pivx.conf remains
(`gen=1`), so mining resumes after the next restart unless you also run
`make deploy-pivx`.

---

## Adjusting Mining Speed

Edit `group_vars/bootstrap_miners.yml`:
```yaml
bootstrap_mining_threads: 2   # increase for faster block production
```

Or pass as extra var:
```bash
ansible-playbook -i ansible/inventories/testnet6 \
  ansible/playbooks/lifecycle/start_bootstrap_mining.yml \
  -e "bootstrap_mining_threads=4"
```

Note: increasing threads only helps up to the number of physical CPU cores.
1-2 threads is usually sufficient for testnet.

---

## Expected Block Times

At difficulty adjustment targets:
- 1 thread, modern server: ~60 second block times
- Difficulty auto-adjusts; blocks may come faster/slower initially

---

## Verifying Block Propagation

Once blocks are being mined on cb1/cb2/cb3 seeders, verify they propagate to all nodes:
```bash
make verify-readiness
```

If some instances show height 0 while miners show height > 5, check peering:
```bash
ssh root@<stalled-host>
pivx-cli -conf=/etc/pivx/<instance>/pivx.conf getconnectioncount
# Should be > 0
pivx-cli -conf=/etc/pivx/<instance>/pivx.conf getpeerinfo | grep addr
```

Ensure seed node IPs are in `pivx_seed_nodes` in `group_vars/all/main.yml`.

---

## What Happens Next

When height reaches ~201, proceed to: **[TRANSITION_TO_POS.md](TRANSITION_TO_POS.md)**
