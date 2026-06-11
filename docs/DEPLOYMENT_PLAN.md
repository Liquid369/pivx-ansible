# Deployment Plan — PIVX Testnet6

## Prerequisites

### On your control machine

- Ansible >= 2.14 (`pip install ansible`)
- Python 3.9+
- ansible-lint (optional, for `make lint`)
- SSH key `~/.ssh/tn6_deploy_key` with access to all fleet hosts

```bash
pip install -r requirements.txt
```

### On fleet servers

- Ubuntu 22.04 LTS (fresh install)
- `deploy` user with passwordless sudo
- SSH access from control machine

### External requirements before first deploy

1. **PIVX testnet6 binary** — confirm the release tag and SHA256 checksum.
   Update `pivx_version`, `pivx_archive_url`, `pivx_checksum` in
   `group_vars/all/main.yml`.

2. **Real IP addresses** — replace all `203.0.113.x` / `2001:db8::` placeholders
   in all `host_vars/*.yml` files.

3. **Vault** — populate `group_vars/all/vault.yml`:
   ```bash
   cp ansible/inventories/testnet6/group_vars/all/vault.yml.example \
      ansible/inventories/testnet6/group_vars/all/vault.yml
   # Edit vault.yml with real values
   ansible-vault encrypt ansible/inventories/testnet6/group_vars/all/vault.yml
   echo "VAULT_PASS" > vault_pass.txt
   chmod 600 vault_pass.txt
   ```

4. **Bootstrap mining addresses** — set or be ready to generate
   (mining rewards go to each seeder instance's own wallet — no address needed).
   These seed instances mine the first blocks and hold the first test coins.

5. **DMN BLS operator keys** — generate these later, after the network is
   staking and collateral is available. Leave `bls_operator_key: REPLACE_ME`
   until an instance is actually being registered as a masternode.

---

## Phase 1 — OS Bootstrap

```bash
make bootstrap
```

This runs `playbooks/bootstrap.yml` on the 15 Contabo lab hosts plus `tn6-infra01`:
- Installs common packages
- Creates `pivx` user
- Configures NTP (chrony)
- Tunes sysctl
- Enables ufw with SSH + PIVX p2p ports
- Sets hostname to `host_label`

**Verify**: Check no failures. SSH to one host and confirm `pivx` user exists.

---

## Phase 2 — Deploy Tor Hidden Services

```bash
make deploy-tor
```

This installs Tor and creates hidden service directories on all 15 masternode
hosts. After completion, **onion addresses are printed to stdout**.

**Action required**: Record every onion address. You will need these for your
DMN registration transactions. The format is:
```
tn6-cb1-tor-mn05: abcdefghijklmnop.onion
```

Do NOT proceed with DMN registration until you have all 30 onion addresses.

---

## Phase 3 — Fresh Chain Deployment

```bash
make deploy
```

This deploys PIVX, all configured instances, Tor, and monitoring. The three
seed instances on `tn6-cb1..tn6-cb3` provide initial connectivity for the fresh
network. At this point the chain may still be at height 0.

**Verify**:
```bash
make status
make verify-readiness
```

---

## Phase 4 — Bootstrap Mining and Initial Coin Supply

```bash
make start-bootstrap-mining
make verify-readiness
```

The colocated seed instances mine the initial PoW blocks. Mine at least to
`mining_phase_target_height` so PoS can activate, and remember that additional
staking time may be required to create and mature enough collateral for the full
90-masternode target.

---

## Phase 5 — Transition to PoS and Stake

```bash
make transition-to-pos
# Edit group_vars/all/main.yml: lifecycle_phase: staking
make deploy-pivx
make enable-staking
```

Fund staking wallets from the mining reward wallets, unlock them for staking,
and let the chain advance through PoS until enough funds/collateral are mature.

---

## Phase 6 — DMN Registration (external to this repo)

Using your PIVX wallet on a separate machine:

1. Send collateral (10,000 PIVX) for each of the 90 masternode instances
2. Register each DMN with `protx register` providing:
   - Collateral txid
   - IPv4 IP:port for IPv4 instances
   - IPv6 [::]:port for IPv6 instances
   - onion:port for Tor instances
   - BLS operator public key (derived from the private key in host_vars)

After registration, populate `bls_operator_key` (private key) in each
host_vars instance entry.

---

## Phase 7 — Enable Masternode Instances

```bash
make deploy-pivx
make enable-masternodes
```

This renders masternode config for registered instances and verifies DMN status.
Enable a small cohort first if you want a lower-risk rollout, then scale toward
the full active topology.

**Verify**: `make status` — should show all instances starting/syncing.

---

## Phase 8 — Deploy or Refresh Monitoring Stack

```bash
make deploy-monitoring
```

1. Installs `node_exporter`, `process-exporter`, and `vector` on all active hosts
2. On `tn6-infra01`: installs Prometheus, Loki, Grafana, Alertmanager

**Verify**:
- Browse to Grafana: `http://<tn6-infra01-ip>:3000`
- Login: admin / `vault_grafana_admin_password`
- Check "Testnet6 Fleet Overview" dashboard

---

## Phase 9 — v6.0 Feature Migration

Once the seed mesh, staking, and masternodes are stable, upgrade to the selected
v6.0 test binary and begin feature-specific validation:

```bash
# Edit group_vars/all/main.yml with the chosen v6.0 artifact/checksum
make upgrade-pivx PIVX_VERSION=6.0.0-test
make status
make verify-readiness
```

See [runbooks/MIGRATE_TO_V6_FEATURES.md](../runbooks/MIGRATE_TO_V6_FEATURES.md).

---

## Phase 10 — Sync Wait

All instances need to sync to chain tip before quorum testing begins. For testnet6
this may take minutes (fresh chain) or hours (if there's existing history).

Monitor via:
```bash
make status
# or per-instance:
pivx-cli -conf=/etc/pivx/tn6-cb1-v4-mn01/pivx.conf \
         -datadir=/var/lib/pivx/tn6-cb1-v4-mn01 \
         getblockchaininfo | jq '.blocks,.headers'
```

---

## Phase 11 — Quorum Verification

Once all instances are synced:

```bash
# On observer (tn6-infra01 / tn6-obs01 instance):
pivx-cli -conf=/etc/pivx/tn6-obs01/pivx.conf \
         -datadir=/var/lib/pivx/tn6-obs01 \
         listquorums
```

Expected: All registered DMNs appear in the quorum list.

---

## Teardown

To stop all PIVX instances across the fleet:

```bash
ansible-playbook -i ansible/inventories/testnet6 \
  -m systemd -a "name='pivxd@*.service' state=stopped" \
  ansible/inventories/testnet6 --become
# Or more precisely:
make cohort-stop COHORT=ipv4
make cohort-stop COHORT=ipv6
make cohort-stop COHORT=tor
```

Data directories persist. To full-reset an instance, delete its `datadir`.
