# Collateral, DMN registration, and wallet upkeep

Numbers here are read off the running chain and `src/chainparams.cpp` on the
`2026_testnet6` branch, not estimated.

| Value | Source | Number |
|---|---|---|
| PoW block reward | block 1 coinbase | 60,001 PIV |
| Masternode collateral | `nMNCollateralAmt` | 10,000 PIV |
| Collateral confirmations | `nMNCollateralMinConf` | 15 |
| Coinbase maturity | `nCoinbaseMaturity` | 15 |
| PoS activation | `UPGRADE_POS` | height 201 |
| Masternodes planned | 10 hosts x 6 | 60 |

## The timing is not tight

60 masternodes need 600,000 PIV. At 60,001 PIV per PoW block that is **ten
blocks of mining**. Mine 20 and there is double the collateral plus fees.

A comfortable schedule, with the deadline being "registered and 15-confirmed
before height 201":

| Height | Step |
|---|---|
| 1-20 | mine (1.2M PIV, 20 coinbase outputs) |
| 35 | block 20's coinbase matures (mined height + 15) |
| ~40 | run the 60 registrations |
| ~45 | registration txs confirmed |
| ~60 | collateral has its 15 confirmations, DMNs ready |
| 60-200 | keep mining, nothing left to do |
| 201 | PoS activates with the full quorum already in place |

That leaves roughly 140 blocks of slack. The failure mode to avoid is not
running out of time, it is starting the registrations before the coinbase has
matured and getting "insufficient funds" on a wallet that visibly holds
1.2M PIV.

## Registration uses one transaction, not two

`protx_register_fund` creates the collateral output and the ProRegTx together:

```
protx_register_fund "collateralAddress" "ipAndPort" "ownerAddress" \
    "operatorPubKey" "votingAddress" "payoutAddress"
```

So there is no separate "send 10,000 then register against it" step, and no
consolidation needed beforehand: each 60,001 PIV coinbase output funds six
registrations with room for fees.

Order of operations per masternode:

1. On the masternode instance: `generateblskeypair`. Keep the secret, take the
   public.
2. Put the secret in `bls_operator_key` in that host's host_vars (it currently
   reads `REPLACE_ME`) and run `make deploy-pivx LIMIT=<host>` so the instance
   starts with `mnoperatorprivatekey`.
3. From a **seeder** wallet, which is where the mined coins are, run
   `protx_register_fund` with that instance's public IP:port and the operator
   public key from step 1.
4. `protx_list` to confirm, then `make enable-masternodes` to verify DMN state
   across the fleet.

The seeder wallet pays and owns the collateral; the masternode instance only
holds the operator key. That split is deliberate — an operator key cannot move
the collateral, so the masternode hosts stay less sensitive than the seeders.

## Where wallet fragmentation actually bites

Not during the PoW phase: one block is one 60,001 PIV output, and the wallet
stays a handful of large UTXOs.

It bites after PoS activates. Staking splits stakes, and masternode payments
arrive as 3 or 6 PIV outputs per hit across 60 nodes. Over a few thousand
blocks a wallet accumulates thousands of small outputs, transactions get large
and slow to sign, and assembling a fresh 10,000 PIV collateral for a
replacement masternode means gathering hundreds of inputs.

Watch it with:

```
make wallet-report                       # balances + UTXO counts, read-only
make wallet-report LIMIT=tn6-cb1
```

`collateral_ready_utxos` counts outputs already >= 10,000 PIV. If a wallet has
a large balance but zero of those, it needs consolidating before it can fund a
registration.

Sweep when a wallet drifts past a few hundred UTXOs:

```
make consolidate INSTANCE=tn6-cb1-seed01
make consolidate INSTANCE=tn6-cb1-seed01 CONSOLIDATE_MIN_UTXOS=50
```

It sends the spendable balance to a fresh address in the same wallet with the
fee subtracted, so there is no change output and the result is one UTXO.
Registered collateral is locked by pivxd and is not swept.

Consolidating pauses staking on the coins involved until the sweep confirms
and re-matures, so do it deliberately rather than on a timer.
