# PIVX Testnet6 — Quickstart

**Audience**: Engineer with root access to the active Contabo Ubuntu 22.04 hosts, basic shell
familiarity, no prior Ansible expertise required.

**Goal**: Get from 15 Contabo servers to an active PIVX testnet with seed
connectivity, staking, LLMQ quorums, and a clean path to v6.0 feature testing.

Estimated time: 2–4 hours (most time is mining PoW blocks).

---

## Before You Start

### Requirements on your local machine
```bash
# Ansible (2.14+)
pip3 install ansible ansible-lint

# Ansible collections
ansible-galaxy collection install community.general ansible.posix

# SSH key access to the 15 Contabo lab hosts plus tn6-infra01
ssh-copy-id root@<each-host-ip>
```

### What you need to know about your servers
- IP address of each of the 15 Contabo masternode hosts plus `tn6-infra01`
- SSH user / key
- Which Contabo hosts are 4 vCPU (`tn6-cb1..tn6-cb7`) versus 6 vCPU (`tn6-cb8..tn6-cb15`)
- IPv4, extra IPv4, IPv6, and second IPv6 assignments for each host

---

## Step 1 — Fill in the inventory

Open `ansible/inventories/testnet6/host_vars/` — there is one `.yml` file per host.

**Find and replace every `REPLACE_ME`** in the following files:
```
host_vars/tn6-cb1.yml       → IPs, BLS keys later
host_vars/tn6-cb2.yml       → IPs, BLS keys later
host_vars/tn6-cb3.yml       → IPs, BLS keys later
host_vars/tn6-cb4..cb15.yml → IPs, BLS keys later
host_vars/tn6-infra01.yml   → IPs
```
Current active seeders are colocated on:

```text
```

**IP addresses**: set `ansible_host` in each file.

**RPC passwords**: generate a unique password per instance. Use:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

**Mining rewards**: paid automatically to each seeder instance's own
wallet during bootstrap mining — no mining address needs configuring.

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

**Expected duration**: ~10–15 minutes for the active fleet (mostly binary download time).

### Verify deployment
```bash
make status
make verify-readiness
```

All instances should be running and able to reach the three colocated seed
instances. The chain can still be at 0 blocks until mining starts.

---

## Step 4 — Bootstrap mining and initial coins (Phase 2)

PIVX testnet starts with PoW. You need to mine at least the PoS activation
height, currently modeled as ~201 blocks, before PoS blocks are valid. These
mined rewards also become the first pool of coins for staking wallets and later
masternode collateral.

### 4a — Set mining address
Mining rewards accrue in each seeder instance's own wallet — nothing to
configure before starting.

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

For the full 90-masternode target, 201 blocks may not produce enough spendable
collateral. Treat 201 as the minimum transition height, then continue building
and maturing funds through staking before registering every masternode.

---

## Step 5 — Transition to PoS and fund stakers (Phase 3)

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

## Step 6 — Enable staking and mature funds (Phase 4)

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

Keep this phase running until the wallets have enough mature outputs for the
masternode rollout size you want to test. You can register a small DMN cohort
first, then scale toward all 90 masternode instances as collateral matures.

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

## Step 8 — Migrate to the v6.0 feature-test binary

Only do this after staking and masternode/quorum health is boring in the best
possible way. That gives you a clean baseline before testing new architecture.

```bash
# Edit group_vars/all/main.yml with the selected v6.0 artifact and checksum
make upgrade-pivx PIVX_VERSION=6.0.0-test
make status
make verify-readiness
```

See [runbooks/MIGRATE_TO_V6_FEATURES.md](../runbooks/MIGRATE_TO_V6_FEATURES.md).

---

## Step 9 — Chaos testing (Phase 7)

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
- Confirm `bls_operator_key` in host_vars matches the `secret` from `generateblskeypair`
- Check `masternode status` via RPC on the instance

---

## Getting Help

- Full lifecycle reference: [docs/LIFECYCLE.md](LIFECYCLE.md)
- Bootstrap mining runbook: [runbooks/BOOTSTRAP_MINING.md](../runbooks/BOOTSTRAP_MINING.md)
- PoS transition runbook: [runbooks/TRANSITION_TO_POS.md](../runbooks/TRANSITION_TO_POS.md)
- Adding a new node: [runbooks/ADD_NODE.md](../runbooks/ADD_NODE.md)
- Open issues / pending items: [REVIEW.md](../REVIEW.md)
