# Collateral, masternodes, and wallet upkeep

Read off `src/chainparams.cpp` and `src/validation.cpp` on the `2026_testnet6`
branch, not estimated.

| Value | Source | Number |
|---|---|---|
| Block 1 reward | `GetBlockValue` premine | 60,001 PIV |
| Blocks 2-200 reward | testnet high-inflation window | 250,000 PIV each |
| Masternode collateral | `nMNCollateralAmt` | 10,000 PIV |
| Collateral confirmations | `nMNCollateralMinConf` | 15 |
| Coinbase maturity | `nCoinbaseMaturity` | 15 |
| PoS activation | `UPGRADE_POS` | 201 |
| v6.0 / deterministic MNs | `UPGRADE_V6_0` | 5000 |

The PoW window pays about 49.75M PIV over blocks 2-200. 60 masternodes need
600,000, so three blocks covers the lot. Funding is not a constraint here.

## The part that actually constrains the schedule

Special transactions are rejected until v6:

```
specialtx_validation.cpp:494
  if (!tx.IsNormalType() && !NetworkUpgradeActive(nHeight+1, UPGRADE_V6_0)) -> reject
```

ProRegTx is a special transaction, so **no deterministic masternode can be
registered before block 5000**. And legacy masternodes go obsolete at the same
height (`LegacyMNObsolete()` is just `NetworkUpgradeActive(nHeight, V6_0)`).

Both edges land on 5000. That means the fleet runs legacy masternodes up to
5000, and every ProRegTx has to be prepared in advance and submitted once the
chain is at 5000 or past it. There is no way to pre-register.

Between 5000 and the moment the registrations confirm, the network has no
masternodes at all. That gap is real and worth measuring, it is the same thing
mainnet will go through.

## Collateral does not need moving

ProRegTx takes referenced external collateral: it looks the outpoint up in the
UTXO set and checks the amount and destination.

```
if (!view->GetUTXOCoin(pl.collateralOutpoint, coin)) -> reject
if (!CheckCollateralOut(coin.out, pl, state, collateralTxDest)) -> reject
```

So the same 10,000 PIV output backing a legacy masternode is reused by the
ProRegTx at 5000. No move, no second 15-confirmation wait, no re-funding. That
only holds if the output is clean: exactly 10,000 PIV, unspent, one output.
Which is the whole reason to cut the collateral outputs early and leave them
alone.

With ~49.75M PIV available there is also nothing stopping a second set of
fresh collateral for a straight v6 registration. Doing some of each is the
better test: reuse covers the migration path real operators will take, fresh
covers the clean path.

## Schedule

| Height | What happens |
|---|---|
| 1-200 | PoW. Block 1 pays 60,001, blocks 2-200 pay 250,000 each |
| 216 | block 201's coinbase matures (mined height + 15) |
| ~220 | cut 60 exact 10,000 PIV collateral outputs |
| ~235 | collateral has its 15 confirmations |
| 201-700 | staged upgrades, see chainparams |
| 235-5000 | legacy masternodes registered and running |
| 5000 | v6 activates. Legacy dies, ProRegTx becomes valid |
| 5000+ | submit the ProRegTx wave, quorums form |

At one minute a block, 5000 is roughly three and a half days from genesis.

## Running the upgrade in waves

Everything cannot restart at once. Two separate things need phasing:

**Binary upgrades** already roll one host at a time:

```
make upgrade-pivx PIVX_VERSION=<ver>
make rolling-restart
```

**The v6 registration wave** is the one to plan. Prepare all 60 ProRegTx
payloads before 5000 (BLS keys generated, collateral outpoints recorded, IPs
and payout addresses fixed), then submit in batches rather than all at once so
a bad payload does not take the whole set with it. Flip the fleet over with:

```
# in group_vars/all/main.yml
masternode_mode: deterministic
make deploy-pivx        # rolls the config change out
```

`masternode_mode` drives whether an instance gets `masternodeprivkey` (legacy)
or `mnoperatorprivatekey` (deterministic). Per-instance `mn_mode` overrides it,
which is how you migrate a subset first.

## Wallet upkeep

Not an issue during PoW: one block is one large output.

It bites once staking and masternode payouts start. Rewards land as 3 or 6 PIV
outputs across 60 nodes, and a wallet ends up with thousands of them.
Transactions get slow to sign, and cutting a fresh 10,000 PIV collateral means
gathering hundreds of inputs.

```
make wallet-report                       # balances + UTXO counts, read-only
make wallet-report LIMIT=tn6-cb1
```

`collateral_ready_utxos` counts outputs already >= 10,000 PIV. A wallet with a
large balance and none of those cannot fund a registration without
consolidating first.

```
make consolidate INSTANCE=tn6-cb1-seed01
make consolidate INSTANCE=tn6-cb1-seed01 CONSOLIDATE_MIN_UTXOS=50
```

Sends the spendable balance to a fresh address in the same wallet with the fee
subtracted, so there is no change output and the result is a single UTXO.
Registered collateral is locked by pivxd and is not swept.

Consolidating pauses staking on those coins until the sweep confirms and
re-matures, so do it deliberately, not on a timer.
