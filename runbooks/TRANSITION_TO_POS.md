# Runbook: PoS Transition (Phase 2 → Phase 3+)

**When to use**: When `make verify-readiness` reports the chain height has
reached `mining_phase_target_height` (default: 201) and you are ready to
stop mining and activate Proof-of-Stake.

---

## Background

PIVX testnet switches from PoW to PoS at block `UPGRADE_POS activation height` (~201).
After this height, PoW blocks are no longer valid — the chain advances only
through PoS block production by staking wallets.

The transition has four sub-steps:
1. Stop runtime mining (`setgenerate false`)
2. Regenerate `pivx.conf` with `gen=0` everywhere
3. Distribute staking PIVX to staking instances
4. Let staking outputs mature before attempting the larger masternode rollout

Phase 3 ("staking") only proceeds once staking nodes have funded, mature UTXOs
and wallets are unlocked.

---

## Prerequisites

- [ ] `make verify-readiness` outputs "READY to transition to PoS"
- [ ] `getblockcount >= mining_phase_target_height` (201) on all synced nodes
- [ ] Staking wallet addresses identified on staking instances
- [ ] Sufficient testnet PIVX on mining nodes to distribute to stakers
  (check with `pivx-cli getbalance` on cb1/cb2/cb3 seeders)

---

## Procedure

### Step 1 — Transition playbook

```bash
make transition-to-pos
```

The playbook will:
1. Assert current height ≥ `mining_phase_target_height`
2. Run `setgenerate false` on all mining instances
3. Re-render `pivx.conf` with `gen=0` for mining instances
4. Restart affected instances
5. Print next-step instructions

### Step 2 — Update lifecycle_phase

After the playbook succeeds, manually update `group_vars/all/main.yml`:
```yaml
lifecycle_phase: staking
```

Then push to all instances:
```bash
make deploy-pivx
```

This ensures pivx.conf is re-rendered with `gen=0` everywhere and logging
labels reflect the new phase.

### Step 3 — Fund staking wallets

Get the receiving addresses from each staking instance:
```bash
ssh root@<host>
pivx-cli -conf=/etc/pivx/<staking-instance>/pivx.conf getnewaddress
```

From the first seeder (which has mining rewards):
```bash
ssh root@<tn6-cb1-ip>
# Send to each staking address:
pivx-cli -conf=/etc/pivx/tn6-cb1-seed01/pivx.conf \
  sendtoaddress "<staking-address>" 10.0
```

Repeat for each staking instance. Each instance needs ≥ 1 PIVX in a
mature UTXO (>200 block confirmations before staking becomes active). Later,
masternode collateral UTXOs also need to mature before registration/activation,
so keep this funding plan separate from the minimal staking-fuel plan.

**Maturity wait**: At 60-second block times, 200 blocks ≈ 3-4 hours.
Plan accordingly; you can move on to masternode setup in parallel.

### Step 4 — Enable staking per instance

Once UTXOs are funded AND mature (>200 confirms):

Update `host_vars/<host>.yml` for each staking instance:
```yaml
staking_enabled: true
```

Then:
```bash
make deploy-pivx    # pushes staking=1 in pivx.conf
```

Unlock each staking wallet:
```bash
ssh root@<host>
pivx-cli -conf=/etc/pivx/<instance>/pivx.conf \
  walletpassphrase "<passphrase>" 9999999 true
```

Verify staking is active:
```bash
make enable-staking
```

Expected output per instance:
```json
{
  "walletunlocked": true,
  "walletconnected": true,
  "walletactive": true,
  "staking status": true
}
```

---

## Common Problems

### "Height below threshold" assertion fails
Mining hasn't reached 201 yet. Check:
```bash
make verify-readiness
```
Wait for it to report READY.

### Instance restarts but chain height drops or stalls
Check that the colocated seed instances are still reachable:
```bash
pivx-cli -conf=/etc/pivx/<instance>/pivx.conf getpeerinfo
```

### `staking status: false` after enabling
Most common causes:
1. UTXOs not mature (< 200 confirmations). Wait.
2. Wallet not unlocked. Re-run `walletpassphrase` command.
3. Not enough peers. Check `getconnectioncount`; min is `min_peer_count` (default 2).

### Wrong passphrase on wallet
If wallet was created with a passphrase you no longer know, you'll need to
restore from the backup mnemonic or wallet.dat file.

---

## What Happens Next

After staking is verified, keep the chain running until enough collateral is
mature. Then register masternodes in waves: start with a small cohort to confirm
DMN registration and quorum behavior, then scale toward the full 90-instance
fleet.

See: **[docs/LIFECYCLE.md — Phase 5](../docs/LIFECYCLE.md#phase-5-masternode--quorum-testing)**

BLS key generation command (run per-DMN-instance):
```bash
pivx-cli -conf=/etc/pivx/<instance>/pivx.conf generateblskeypair
```
Fill in the `secret` value as `bls_operator_key` in the relevant `host_vars` file.
