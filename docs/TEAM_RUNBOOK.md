# Team Runbook — Operating Testnet6 Without the Owner

Start here if you have just been given access. This gets you from zero to
safely running commands, and covers the workflows that the older docs predate.

For depth, the existing docs still stand and are not repeated here:

| Doc | Read it for |
|---|---|
| `QUICKSTART.md` | First-time setup, full deploy from scratch |
| `OPERATIONS.md` | Day-2 tasks, rolling restarts, cohort operations |
| `LIFECYCLE.md` | Phase-by-phase chain bring-up, upgrade ladder |
| `INVENTORY_MODEL.md` | host_vars schema, instance fields, port allocation |
| `OBSERVABILITY.md` | Metric and log schema, Loki queries |
| `ARCHITECTURE.md` | Why the fleet is shaped the way it is |
| `CHAOS_TESTING.md` | Failure injection scenarios |

---

## 1. Access

You need three things. Ask the fleet owner for all three; none can be
self-served.

1. **Your SSH public key added to `ops_ssh_keys`** in
   `inventories/testnet6/group_vars/all/main.yml`, then rolled out with
   `make bootstrap`. Password auth is off fleet-wide, so this list is the only
   door.
2. **The ansible-vault password.** Nearly every playbook reads
   `group_vars/all/vault.yml` (RPC passwords, Grafana admin, masternode keys).
   Without it playbooks fail immediately on decrypt.
3. **Grafana login** at `grafana.liquid369.wtf`.

`vault.yml` is deliberately **not in git**. If you do not have it, you cannot
reconstruct it — ask.

### Verify your access works

```bash
make check-inventory          # parses inventory, no host contact
ansible all -m ping           # proves SSH to all 16 hosts
make status                   # proves vault decrypt + RPC on every instance
```

If `ansible all -m ping` succeeds but `make status` fails on decrypt, you have
SSH but not the vault password.

---

## 2. Rules that are not obvious

**Never run a fleet-wide playbook you have not scoped first.** Everything takes
`LIMIT`:

```bash
make deploy-pivx LIMIT=tn6-cb1        # one host
make deploy-pivx                       # all 15 — takes over an hour
```

Deploys are per-host serial and each host takes 4–20 minutes. A fleet-wide run
that gets killed halfway leaves queued handlers unrun, which means config
written but services not restarted. **If a run dies, re-run it for the hosts it
did not reach rather than assuming it finished.**

**Check what a change restarts.** Editing `pivx.conf.j2` or any host_vars
instance block restarts every affected pivxd. With 145 masternodes registered,
a fleet-wide restart is survivable but not free — see the expiry timings in
section 4.

**Do not hand-edit anything under `/etc/pivx/` on a host.** It is generated and
the next deploy overwrites it. Change the template or host_vars.

**`switchover/` and `vault.yml` are gitignored and contain live secrets.**
Never commit them, never paste their contents into chat or tickets.

---

## 3. Daily checks

```bash
make status                    # per-instance height, peers, service state
```

Grafana `tn6-chain` dashboard is the faster read. What "healthy" looks like:

- 159 instances running, 0 failed
- All heights within a block or two of each other
- `ChainForkDetected` silent
- 145 masternodes enabled
- Tip age under a minute or so while staking

A quick fleet-wide consensus check without Grafana:

```bash
ansible all -f 20 -m shell -a 'pivx-cli -conf=/etc/pivx/<instance>/pivx.conf getblockcount'
```

Comparing block **hashes** at a fixed height is the real fork test, not heights.
Nodes legitimately differ by a block or two during propagation.

---

## 4. The chain must keep moving

This is the failure mode that will bite you if you inherit the fleet quietly.

`UpdateBlockchainSynced` marks a node unsynced once its tip is older than **60
minutes**. `CActiveMasternode::ManageStatus` refuses to send a masternode ping
while unsynced. A masternode that stops pinging goes EXPIRED at **120 minutes**
and is REMOVED at **130**.

So a stalled chain silently de-registers the entire tier two.

While staking is healthy this takes care of itself — blocks land every ~15s.
It matters when:

- The chain is below the PoS activation height (nothing produces blocks on its
  own; `make chain-keepalive` mines to keep the tip fresh)
- Staking stops for any reason

`ChainTipStale` fires at 300s, well before the 3600s cutoff. **Treat it as
urgent** — you have roughly 45 minutes from a genuine stall before masternodes
start expiring.

Recovery if they do expire is not painful: mine or wait for a block, confirm
`mnsync status` shows `IsBlockchainSynced: true`, then re-broadcast:

```bash
make setup-legacy-masternodes START=true
```

Collateral stays locked and `masternode.conf` is untouched, so this is a
re-broadcast, not a rebuild. Allow ~10 minutes for PRE_ENABLED to become
ENABLED — a node needs its ping to be 600s newer than its broadcast.

---

## 5. Masternode workflows

Order matters and the playbooks assume the previous step is done.

```bash
make create-collateral COUNT=<n>       # cut and lock 10000 PIV outputs
make generate-mn-keys                  # one key per MN-capable instance
# merge output into group_vars/all/vault.yml as vault_mn_legacy_keys
make deploy-pivx                       # push keys + masternodeaddr to instances
make setup-legacy-masternodes          # write masternode.conf, do not start
make setup-legacy-masternodes START=true   # broadcast
```

**MN-capable** is not the same as "is a masternode instance". `CheckDefaultPort`
rejects any masternode not announcing the network default port (51474), so
`v4-mn02` — which shares its host's single IPv4 on port 51484 — can never be
one. The same rule is applied in the key generator, the metrics collector and
`setup_legacy_masternodes.yml`; do not hand-roll a different one.

Collateral must have **15 confirmations** (`nMNCollateralMinConf`) before
`startmasternode` will accept it. Depth is `tip - utxoHeight + 1`, so an output
mined in block N is eligible at N+14.

`startmasternode` also refuses while the chain is not synced, which is the same
60-minute tip freshness rule as above. If a start attempt returns
`Sync in progress`, the chain is stale — get a block in first.

---

## 6. Things that cost us hours

Each of these looked like something else at first.

**A deploy that reports `changed` may have changed nothing that matters.** The
explorer sat 5000 blocks behind because its binary install was guarded on the
file merely existing, so it kept a stale binary through every deploy while
reporting success. Verify the thing you intended to change, not the exit code.

**`getbalance` counts locked coins.** Coins locked as masternode collateral are
in the balance but can never be selected by `sendmany`. Use `listunspent` for
anything that needs actually-spendable funds.

**`lockunspent` validates the whole batch and locks nothing if any outpoint is
already locked.** Send only the difference against `listlockunspent`.

**`lockunspent` locks live in memory only.** They vanish on restart. The
protection that survives is `-mnconflock` (default on), which re-locks whatever
is in `masternode.conf` at startup. Before `masternode.conf` existed, a restart
plus a `sendmany` destroyed six collateral outputs.

**Zero inbound peers is usually not a fault.** Only one outbound connection per
netgroup is permitted (`net.cpp`), and the fleet's 45 IPv4 addresses sit in 10
netgroups. Instances in a crowded group get no inbound however reachable they
are. A *cohort-wide* loss of inbound is the real signal.

**Debug categories `net` and `net_mn` trace every P2P message.** They produced
2000+ lines per minute per instance and 55GB fleet-wide. They are off. Turn
either back on for one instance without a restart:

```bash
pivx-cli -conf=<conf> logging '["net_mn"]' '[]'
```

**A stale tip breaks more than it looks like.** See section 4.

---

## 7. Long-running commands

The control node is a laptop and long ansible runs get killed. For anything
fleet-wide, run it detached and poll rather than watching it:

```bash
nohup make deploy-pivx > /tmp/deploy.log 2>&1 & disown
tail -f /tmp/deploy.log
```

Per-host loops are more reliable than one fleet-wide run — a killed run loses
queued handlers, a killed loop only loses the host it was on.

---

## 8. Secrets

- `vault.yml` — RPC passwords, Grafana admin, masternode keys, spork key.
  Gitignored, mode 0600, exists only on operator machines.
- `switchover/` — collateral outpoints and generated masternode keys.
  Gitignored.
- **The spork key signs consensus-level messages.** Its public half is compiled
  into `chainparams.cpp`, so it cannot be rotated without a new binary and a
  fleet-wide upgrade. It is deliberately **not** deployed to any host. If you
  need to set a spork, sign from a local node rather than putting the key on a
  rented VPS.

Rotate the vault password and re-encrypt if anyone with access leaves:

```bash
ansible-vault rekey inventories/testnet6/group_vars/all/vault.yml
```

---

## 9. Who to escalate to

Anything touching the spork key, chainparams, the ProRegTx wave, or retiring
legacy masternodes is a coordinated change — talk to the fleet owner first.
Those are one-way doors and several depend on ordering that is not enforced by
any playbook.
