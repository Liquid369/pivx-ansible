# PIVX Testnet6 — Testnet Lifecycle Guide

This document describes the five lifecycle phases of the PIVX Testnet6 quorum-testing environment, the preconditions required before each phase transition, and the exact commands needed to execute each transition.

---

## Lifecycle Phases

```
Phase 1: fresh_chain       — fresh chain deployed, no blocks yet
Phase 2: bootstrap_mining  — PoW mining to build chain height
Phase 3: pos_transition    — mining stops; wallets fund staking UTXOs
Phase 4: staking           — wallets actively staking for block rewards
Phase 5: masternode_quorum — DMNs registered; LLMQ quorums active
Phase 6: chaos_testing     — fault injection tests running
```

The `lifecycle_phase` variable in `group_vars/all/main.yml` controls which
configuration blocks are rendered in `pivx.conf` on the next `make deploy-pivx`.

---

## Phase 1: Fresh Chain Bring-Up

### What this does
Deploys all 15 hosts from a clean slate: OS packages, pivx user/dirs,
PIVX 5.6.1 binary, Sapling params, pivx.conf (gen=0), systemd units, Tor, monitoring.

### Preconditions
- All 15 hosts reachable via SSH
- `host_vars/*.yml` filled in (see `REVIEW.md` for REPLACE_ME checklist)
  - `rpc_password` set per instance
  - `bootstrap_mining_address` set in seed01/seed02 host_vars
- SSH public key deployed on all hosts

### Commands
```bash
# 1. OS prep (once per host lifetime)
make bootstrap

# 2. Deploy everything
make deploy

# 3. Check fleet came up
make status
make verify-readiness
```

### Expected result
All instances running, 0 blocks, connected to seed nodes.
pivx-cli getblockchaininfo → blocks: 0

---

## Phase 2: Bootstrap Mining

During Phase 2, tn6-seed01 and tn6-seed02 act as CPU miners.
They mine blocks to build the chain height past `nFirstPoSBlock`
(set as `mining_phase_target_height` in group_vars, default: 201).

Below that height, PIVX testnet uses PoW (CPU mining).
Above it, PoS becomes valid.

### Preconditions
- Phase 1 complete, fleet healthy
- `group_vars/all/main.yml`: `lifecycle_phase: bootstrap_mining`
- `host_vars/tn6-seed01.yml` and `tn6-seed02.yml`:
  - `mining_enabled: true`
  - `bootstrap_mining_address: "<TESTNET_ADDRESS_WITH_FUNDS>"` (replace!)
- `make deploy-pivx` run to push updated pivx.conf (sets gen=0 on non-miners)

### Commands
```bash
# Edit group_vars/all/main.yml: lifecycle_phase: bootstrap_mining
# Edit seed01/seed02 host_vars: mining_enabled: true

# Push new pivx.conf to all instances
make deploy-pivx

# Activate runtime mining on seed01 + seed02 (setgenerate true)
make start-bootstrap-mining

# Monitor height
make verify-readiness
# Outputs: "Mining in progress (N/201)" until ready
```

### Monitoring
- Grafana: "Block Height" panel shows height climbing
- `make verify-readiness` polls every run — rerun manually or in a watch loop:
  ```bash
  watch -n 30 make verify-readiness
  ```

### Expected result
`make verify-readiness` outputs:
```
STATUS: READY to transition to PoS — run: make transition-to-pos
```

---

## Phase 3: PoS Transition

Stops mining, regenerates pivx.conf with `gen=0`, restarts instances.

### Preconditions
- Phase 2 complete: `getblockcount >= mining_phase_target_height` (201)
- `make verify-readiness` reports READY
- Staking wallet addresses funded on staking instances (≥1 PIVX per instance for minimal testing)

### Commands
```bash
# Transition (stops mining, sets gen=0, rebuilds conf, restarts)
make transition-to-pos

# Ansible will:
# 1. Verify height threshold
# 2. Call setgenerate false on mining instances
# 3. Set lifecycle_phase → pos_transition internally
# 4. Regenerate pivx.conf (gen=0) and restart instances

# After transition — manually edit group_vars/all/main.yml:
# lifecycle_phase: staking
make deploy-pivx   # push final gen=0 conf everywhere
```

### Expected result
All instances running, no mining activity, chain advancing via PoS.
`getmininginfo` → `networkhashps: 0`

---

## Phase 4: Staking

Instances with `staking_enabled: true` in host_vars actively stake.

### Preconditions
- Phase 3 complete
- `group_vars/all/main.yml`: `lifecycle_phase: staking`
- Each staking instance wallet:
  - Unlocked for staking: `walletpassphrase "<pass>" 99999999 true`
  - Has mature UTXOs (>200 block confirmations at ≥1 PIVX each)
- `make deploy-pivx` run to push `staking=1` in pivx.conf

### Commands
```bash
# Edit group_vars/all/main.yml: lifecycle_phase: staking
# Edit host_vars for staking instances: staking_enabled: true
make deploy-pivx

# Verify staking is active
make enable-staking
# Outputs getstakingstatus per instance
```

### Verifying staking per instance
```bash
# SSH to a staking host, then for each instance:
pivx-cli -conf=/etc/pivx/tn6-cb1/pivx.conf getstakingstatus
# Should show:
# "walletunlocked": true
# "walletconnected": true (enough peers)
# "walletactive": true
# "staking status": true
```

### Expected result
New PoS blocks appearing in chain explorer.
`getstakingstatus` returns `"staking status": true` on staking instances.

---

## Phase 5: Masternode / Quorum Testing

This is the target state for quorum failure and resilience tests.

### Preconditions
**These must be done IN THIS ORDER:**

1. **BLS key generation** (per DMN instance):
   ```bash
   pivx-cli bls generate
   # → { "secret": "...", "public": "..." }
   ```
   Fill `bls_operator_key` in `host_vars/<host>.yml` for each masternode instance.

2. **Collateral UTXOs** — 10,000 PIVX testnet per masternode, unspent in the
   operator wallet. Get testnet coins from the testnet faucet or mine more blocks.

3. **ProRegTx** — register each DMN on-chain using PIVX Core wallet:
   ```
   protx register_prepare <collateral_txid> <collateral_index> ...
   protx register_submit ...
   ```
   This is done outside Ansible. See PIVX documentation.

4. **Update host_vars**:
   ```yaml
   masternode_enabled: true
   bls_operator_key: "<secret_bls_key>"
   ```

5. **Update group_vars**:
   ```yaml
   lifecycle_phase: masternode_quorum
   masternode_enabled: true   # global default for masternode group
   ```

6. **Push pivx.conf** with masternode config:
   ```bash
   make deploy-pivx   # renders masternode=1 + masternodeblsprivkey block
   ```

### Commands
```bash
# After completing all prerequisites above:
make enable-masternodes
# Shows masternode status per instance and DMN registration status
```

### Verifying quorum formation
```bash
# Check DKG status
pivx-cli -conf=/etc/pivx/tn6-cb1/pivx.conf quorum dkgstatus

# List active quorums
pivx-cli -conf=/etc/pivx/tn6-cb1/pivx.conf quorum list

# Check specific quorum info
pivx-cli -conf=/etc/pivx/tn6-cb1/pivx.conf quorum info <llmq_type> <quorum_hash>
```

### Expected result
All DMNs show `"status": "READY"` in `masternode status`.
`quorum list` shows at least one active LLMQ quorum.

---

## Phase 6: Chaos Testing

With quorums active, inject network faults to test resilience.

### Latency injection
```bash
# Add 200ms ± 20ms latency to all Tor cohort hosts
make chaos-inject-latency COHORT=tor DELAY=200ms JITTER=20ms

# IPv6 cohort with 300ms latency
make chaos-inject-latency COHORT=ipv6 DELAY=300ms JITTER=50ms
```

### Packet loss injection
```bash
make chaos-inject-loss COHORT=ipv4 LOSS=10
```

### Cohort stop/start
```bash
# Stop entire Tor cohort (simulates Tor network outage)
make cohort-stop COHORT=tor

# Restore
make cohort-start COHORT=tor
```

### Clear all fault injection
```bash
make chaos-clear COHORT=tor
make chaos-clear COHORT=ipv6
make chaos-clear COHORT=ipv4
```

### Collect debug bundle
```bash
make collect-debug
# Pulls logs, getblockchaininfo, getmasternode list, quorum dkgstatus
# from all instances and archives locally
```

---

## Restarting the Chain from Genesis

To wipe the entire chain and start over (e.g., after a test run):

```bash
# Preview what would be wiped (no changes made)
make wipe-chain-dry-run

# Full wipe — wallets preserved by default
make wipe-chain

# Wipe including wallets (DESTRUCTIVE — no recovery)
ansible-playbook -i ansible/inventories/testnet6 \
  ansible/playbooks/lifecycle/wipe_chain.yml \
  -e "chain_wipe_keep_wallet=false"

# After wipe, reset lifecycle_phase
# Edit group_vars/all/main.yml: lifecycle_phase: bootstrap_mining
# Then restart from Phase 1:
make deploy
make start-bootstrap-mining
```

---

## Lifecycle Phase Quick Reference

| Phase                  | `lifecycle_phase` value    | pivx.conf effect                    |
|------------------------|----------------------------|--------------------------------------|
| Fresh chain            | `bootstrap_mining`          | gen=0 (before mining starts)         |
| Mining active          | `bootstrap_mining`          | gen=1, genproclimit=N on miners      |
| Transition             | `pos_transition`            | gen=0 everywhere                     |
| Staking                | `staking`                  | staking=1 on staking instances       |
| Masternodes + quorums  | `masternode_quorum`         | masternode=1 + blsprivkey on DMNs    |
| Chaos testing          | `chaos_testing`             | same as masternode_quorum            |

---

## Confirming `nFirstPoSBlock`

The `mining_phase_target_height` default of `201` is a placeholder based on
typical PIVX testnet parameters. **Confirm the actual value** before starting
Phase 2:

```bash
grep -r "nFirstPoSBlock\|nPosStartHeight" <pivx-core-src>/src/chainparams.cpp
```

Or ask the PIVX devs for the testnet value and update:
```yaml
# group_vars/all/main.yml
mining_phase_target_height: 201   # ← update if different
```
