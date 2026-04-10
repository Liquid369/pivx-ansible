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

4. **DMN BLS operator keys** — generate BLS keypairs for each of the 36 masternode
   instances. Populate `bls_operator_key` in each instance dict in host_vars.
   DO NOT commit real keys.

---

## Phase 1 — OS Bootstrap

```bash
make bootstrap
```

This runs `playbooks/bootstrap.yml` on all 15 hosts:
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

This installs Tor and creates hidden service directories on all 12 masternode
hosts. After completion, **onion addresses are printed to stdout**.

**Action required**: Record every onion address. You will need these for your
DMN registration transactions. The format is:
```
tn6-cb1-tor-mn03: abcdefghijklmnop.onion
```

Do NOT proceed with DMN registration until you have all 12 onion addresses.

---

## Phase 3 — DMN Registration (external to this repo)

Using your PIVX v6.0 wallet on a separate machine:

1. Send collateral (10,000 PIVX) for each of the 36 masternode instances
2. Register each DMN with `protx register` providing:
   - Collateral txid
   - IPv4 IP:port for IPv4 instances
   - IPv6 [::]:port for IPv6 instances
   - onion:port for Tor instances
   - BLS operator public key (derived from the private key in host_vars)

After registration, populate `bls_operator_key` (private key) in each
host_vars instance entry.

---

## Phase 4 — Deploy PIVX Instances

```bash
make deploy-pivx
```

Runs in serial batches (5 hosts at a time). For each host:
1. Downloads and verifies PIVX binary
2. Creates per-instance datadir, confdir, logdir
3. Writes `pivx.conf` and `instance.env` from templates
4. Installs per-instance systemd unit
5. Enables and starts the service
6. Waits for RPC to respond

**Verify**: `make status` — should show all instances starting/syncing.

---

## Phase 5 — Deploy Monitoring Stack

```bash
make deploy-monitoring
```

1. Installs `node_exporter` and `vector` on all 15 hosts
2. On `tn6-infra01`: installs Prometheus, Loki, Grafana, Alertmanager

**Verify**:
- Browse to Grafana: `http://<tn6-infra01-ip>:3000`
- Login: admin / `vault_grafana_admin_password`
- Check "Testnet6 Fleet Overview" dashboard

---

## Phase 6 — Sync Wait

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

## Phase 7 — Quorum Verification

Once all instances are synced:

```bash
# On observer (tn6-infra01 / tn6-obs01 instance):
pivx-cli -conf=/etc/pivx/tn6-obs01/pivx.conf \
         -datadir=/var/lib/pivx/tn6-obs01 \
         quorum list
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
