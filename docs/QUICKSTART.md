# PIVX Testnet6 — Quickstart

**Audience**: Engineer with root access to 15 Ubuntu 22.04 hosts, basic shell
familiarity, no prior Ansible expertise required.

**Goal**: Get from 15 bare servers to an active PIVX testnet with LLMQ quorums
running, ready for chaos testing.

Estimated time: 2–4 hours (most time is mining PoW blocks).

---

## Before You Start

### Requirements on your local machine
```bash
# Ansible (2.14+)
pip3 install ansible ansible-lint

# Ansible collections
ansible-galaxy collection install community.general ansible.posix

# SSH key access to all 15 hosts (root or sudo user)
ssh-copy-id root@<each-host-ip>
```

### What you need to know about your servers
- IP address of each of the 15 hosts
- SSH user / key
- Which hosts are Contabo (IPv4), which are OVH (IPv6), and which run Tor

---

## Step 1 — Fill in the inventory

Open `ansible/inventories/testnet6/host_vars/` — there is one `.yml` file per host.

**Find and replace every `REPLACE_ME`** in the following files:
```
host_vars/tn6-seed01.yml    → ansible_host, rpc_password, bootstrap_mining_address
host_vars/tn6-seed02.yml    → ansible_host, rpc_password, bootstrap_mining_address
host_vars/tn6-cb1.yml       → ansible_host, rpc_password (bls_operator_key: later)
... (repeat for all 15 host_vars files)
```

**IP addresses**: set `ansible_host` in each file.

**RPC passwords**: generate a unique password per instance. Use:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

**Mining address** (`bootstrap_mining_address` in seed01/seed02): any valid
PIVX testnet address. You can generate one later from the pivx-cli wallet
after Phase 1 deployment.

**BLS operator keys** (`bls_operator_key`): generated in Phase 5.
Leave as `REPLACE_ME` for now — masternode instances only.

### Also check
- `group_vars/all/main.yml`: verify `pivx_version: "5.6.1"` is correct
- `group_vars/all/main.yml`: set `lifecycle_phase: bootstrap_mining`
- `group_vars/all/main.yml`: set real seed node IPs in `pivx_seed_nodes`

### Validate inventory
```bash
make check-inventory
```

---

## Step 2 — OS bootstrap (run once)

```bash
make bootstrap
```

This installs system packages, creates the `pivx` OS user/group, sets up
UFW firewall rules, and ensures required kernel modules are loaded.

**If a host fails**: fix the issue on that host and re-run with `LIMIT=<hostname>`:
```bash
make bootstrap LIMIT=tn6-cb1
```

---

## Step 3 — Full deploy

```bash
make deploy
```

This deploys:
- PIVX 5.6.1 binary (`/opt/pivx/releases/5.6.1/`, symlinked to `/opt/pivx/current`)
- Sapling zk-SNARK parameters (`/home/pivx/.pivx-params/`)
- All pivx.conf files (gen=0 at this stage)
- All systemd unit files (`pivxd@<instance>.service`)
- Tor hidden services (if applicable)
- Prometheus, Grafana, Loki, Alertmanager (on the monitoring host)
- Vector log shipper on all PIVX hosts

**Expected duration**: ~10–15 minutes for 15 hosts (mostly binary download time).

### Verify deployment
```bash
make status
make verify-readiness
```

All instances should be running with 0 blocks, connected to seed nodes.

---

## Step 4 — Bootstrap mining (Phase 2)

PIVX testnet starts with PoW. You need to mine ~201 blocks before PoS activates.

### 4a — Set mining address
If you skipped it in Step 1, get a testnet mining address now:
```bash
ssh root@<seed01-ip>
pivx-cli -conf=/etc/pivx/tn6-seed01-instance1/pivx.conf getnewaddress
```
Copy the output address into `host_vars/tn6-seed01.yml` → `bootstrap_mining_address`.
Do the same for seed02.

### 4b — Start mining
```bash
make start-bootstrap-mining
```

### 4c — Monitor progress
```bash
make verify-readiness
# Outputs current height vs. target (201)
```

Or watch continuously:
```bash
watch -n 30 make verify-readiness
```

Mining ~201 blocks with 1 CPU thread takes approximately 30–90 minutes
depending on CPU speed. You can increase `bootstrap_mining_threads` in
`group_vars/bootstrap_miners.yml` to speed it up.

---

## Step 5 — Transition to PoS (Phase 3)

When `verify-readiness` reports "READY to transition to PoS", run:
```bash
make transition-to-pos
```

This:
1. Verifies height ≥ 201
2. Calls `setgenerate false` on all mining instances
3. Regenerates pivx.conf with `gen=0`
4. Restarts affected instances

After this completes:
```bash
# Update lifecycle_phase in group_vars/all/main.yml:
#   lifecycle_phase: staking
make deploy-pivx   # push final gen=0 conf
```

---

## Step 6 — Enable staking (Phase 4)

### 6a — Fund staking wallets
Each staking instance needs mature (>200 confirms) UTXOs ≥ 1 PIVX.

Send testnet PIVX from the mining rewards wallet to each staking instance.
You can use `pivx-cli sendtoaddress` from any instance with balance.

### 6b — Unlock wallets for staking
On each staking instance:
```bash
ssh root@<host>
pivx-cli -conf=/etc/pivx/<instance>/pivx.conf \
  walletpassphrase "<your-passphrase>" 9999999 true
```
(The final `true` means unlock-for-staking-only, not full spending unlock.)

### 6c — Enable staking in host_vars
Edit `host_vars/<host>.yml` for each staking instance:
```yaml
staking_enabled: true
```

Edit `group_vars/all/main.yml`:
```yaml
lifecycle_phase: staking
```

```bash
make deploy-pivx        # pushes staking=1 in pivx.conf
make enable-staking     # verifies getstakingstatus
```

---

## Step 7 — Register masternodes and enable quorums (Phase 5)

This is the most involved step. See [runbooks/TRANSITION_TO_POS.md](../runbooks/TRANSITION_TO_POS.md)
for the detailed PoS/masternode transition and [docs/LIFECYCLE.md](LIFECYCLE.md#phase-5-masternode--quorum-testing)
for full requirements.

### Summary
1. Generate BLS keypairs (one per masternode instance)
2. Send 10,000 tPIVX collateral per masternode
3. Broadcast ProRegTx from PIVX Core wallet (not Ansible)
4. Fill in `bls_operator_key` + `masternode_enabled: true` in host_vars
5. Update `lifecycle_phase: masternode_quorum`
6. `make deploy-pivx && make enable-masternodes`

---

## Step 8 — Chaos testing (Phase 6)

With quorums active:
```bash
# Inject 200ms latency to Tor cohort
make chaos-inject-latency COHORT=tor DELAY=200ms JITTER=20ms

# Inject 10% packet loss to IPv6 cohort
make chaos-inject-loss COHORT=ipv6 LOSS=10

# Stop entire IPv4 cohort
make cohort-stop COHORT=ipv4

# Restore everything
make cohort-start COHORT=ipv4
make chaos-clear COHORT=tor
make chaos-clear COHORT=ipv6

# Collect debug bundle
make collect-debug
```

---

## Monitoring

Grafana is deployed on the monitoring host (check `hosts.yml` for the IP).

Default access: `http://<monitoring-host>:3000`  
Default credentials: admin / admin (change on first login)

Key dashboards:
- **PIVX Fleet** — block heights, peer counts, instance health
- **Lifecycle** — current phase, mining status, staking status
- **Chaos** — active netem rules, cohort fault events

Alerts are sent to the alertmanager. Check `roles/alertmanager/` for
receiver configuration (Slack/email/PagerDuty).

---

## Starting Over (chain wipe)

```bash
# Preview what would be wiped
make wipe-chain-dry-run

# Wipe and restart from genesis
make wipe-chain
# Wallets are preserved by default.

# Reset phase and redeploy
# Edit group_vars/all/main.yml: lifecycle_phase: bootstrap_mining
make deploy
make start-bootstrap-mining
```

---

## Troubleshooting

### Instance won't start
```bash
journalctl -u pivxd@<instance-name> -n 50
# Common causes:
# - Missing Sapling params (re-run make deploy-pivx)
# - Bad pivx.conf (check /etc/pivx/<instance>/pivx.conf)
# - Port conflict (check rpc_port uniqueness per host)
```

### RPC not responding
```bash
pivx-cli -conf=/etc/pivx/<instance>/pivx.conf getblockchaininfo
# If timeout: check service is running and bind_addr is correct
```

### Staking not working
```bash
pivx-cli -conf=/etc/pivx/<instance>/pivx.conf getstakingstatus
# walletunlocked: false → unlock the wallet
# walletconnected: false → not enough peers, check min_peer_count
```

### Masternode not registering
- Confirm ProRegTx was broadcast and confirmed (6+ blocks)
- Confirm `bls_operator_key` in host_vars matches the `secret` from `bls generate`
- Check `masternode status` via RPC on the instance

---

## Getting Help

- Full lifecycle reference: [docs/LIFECYCLE.md](LIFECYCLE.md)
- Bootstrap mining runbook: [runbooks/BOOTSTRAP_MINING.md](../runbooks/BOOTSTRAP_MINING.md)
- PoS transition runbook: [runbooks/TRANSITION_TO_POS.md](../runbooks/TRANSITION_TO_POS.md)
- Adding a new node: [runbooks/ADD_NODE.md](../runbooks/ADD_NODE.md)
- Open issues / pending items: [REVIEW.md](../REVIEW.md)
