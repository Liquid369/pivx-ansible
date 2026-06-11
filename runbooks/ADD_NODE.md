# Runbook: Adding a New Node to the Fleet

**When to use**: When adding a new physical host to an already-running testnet,
or restoring a host that was wiped/rebuilt.

---

## Overview

Adding a node requires:
1. Adding the host to `hosts.yml`
2. Creating a `host_vars/<hostname>.yml` for the new host
3. Adding the PIVX instance definitions for the new host
4. Running bootstrap + deploy targeted at the new host
5. Verifying the node syncs and joins the fleet

---

## Step 1 — Gather host information

You need:
- Hostname (e.g. `tn6-cb16`)
- IP address (`ansible_host`)
- Provider (Contabo/OVH/other)
- Intended protocol cohort (ipv4 / ipv6 / tor)
- Number of PIVX instances to run on this host
- Port ranges available (p2p and RPC ports must be unique per instance per host)
- SSH user and key path

---

## Step 2 — Add to inventory

### hosts.yml

Add the new host to the appropriate groups in `ansible/inventories/testnet6/hosts.yml`:

```yaml
# Example: new Contabo IPv4 host
all:
  children:
    pivx_nodes:
      hosts:
        tn6-cb16:                 # ← new entry
    cohort_ipv4:
      hosts:
        tn6-cb16:                 # ← add to cohort
    masternodes:
      hosts:
        tn6-cb16:                 # ← if it runs masternodes
```

Keep the host in exactly the right groups:
- `pivx_nodes`: always
- `cohort_ipv4` / `cohort_ipv6` / `cohort_tor`: exactly one
- `masternodes` / `bootstrap_miners`: only if applicable
- `monitoring`: only for the dedicated monitoring host

### host_vars

Copy the nearest equivalent host_vars as a starting point:
```bash
cp ansible/inventories/testnet6/host_vars/tn6-cb1.yml \
   ansible/inventories/testnet6/host_vars/tn6-cb16.yml
```

Edit the new file. Minimum required fields to change:
```yaml
ansible_host: "X.X.X.X"      # new host IP
ansible_user: root            # SSH user

pivx_instances:
  - name: tn6-cb16-mn1        # unique across the FLEET, not just the host
    enabled: true
    slot: 1
    protocol_class: ipv4
    cohort: ipv4
    role: masternode
    bind_addr: "0.0.0.0"
    external_ip: "X.X.X.X"
    p2p_port: 51474            # must be unique on this host
    rpc_port: 18382            # must be unique on this host
    rpc_user: pivxrpc
    rpc_password: "REPLACE_ME" # generate: python3 -c "import secrets; print(secrets.token_urlsafe(24))"
    datadir: "/var/lib/pivx/tn6-cb16-mn1"
    logdir: "/var/log/pivx/tn6-cb16-mn1"
    confdir: "/etc/pivx/tn6-cb16-mn1"
    mining_enabled: false
    staking_enabled: false
    masternode_enabled: false  # set true after ProRegTx for this node
    bls_operator_key: "REPLACE_ME"
    extra_conf: ""
```

**Important**: instance `name` and `p2p_port`/`rpc_port` must be unique across
the entire fleet. Check existing host_vars before assigning ports.

### Check for port conflicts
```bash
grep -h "p2p_port\|rpc_port" ansible/inventories/testnet6/host_vars/*.yml | sort | uniq -d
# Should return nothing. Any duplicates are conflicts.
```

---

## Step 3 — Validate inventory

```bash
make check-inventory
```

Fix any errors before proceeding.

---

## Step 4 — Bootstrap the new host

```bash
make bootstrap LIMIT=tn6-cb16
```

This installs packages, creates the `pivx` user, sets up UFW.

---

## Step 5 — Deploy PIVX to the new host

```bash
make deploy-pivx LIMIT=tn6-cb16
```

This installs the binary, Sapling params, pivx.conf, and systemd units.

---

## Step 6 — Deploy monitoring agents

```bash
make deploy-monitoring LIMIT=tn6-cb16
```

This installs node_exporter and Vector on the new host.

---

## Step 7 — Deploy Tor (if applicable)

Only needed if the new host is in the `cohort_tor` group:
```bash
make deploy-tor LIMIT=tn6-cb16
```

After Tor deploys, it prints the newly generated onion address for each hidden
service. Copy those addresses back into `host_vars/tn6-cb16.yml`:
```yaml
onion_address: "xxxxxxxxxxxxxxxxxxxx.onion"
```

Then re-run deploy-pivx to update pivx.conf with the onion address:
```bash
make deploy-pivx LIMIT=tn6-cb16
```

---

## Step 8 — Verify sync

```bash
make verify-readiness LIMIT=tn6-cb16
```

The new node should start syncing from the fleet. Sync time depends on chain
height and network speed — a few minutes for a short testnet chain.

```bash
# Manual check from the host:
ssh root@<new-host-ip>
pivx-cli -conf=/etc/pivx/tn6-cb16-mn1/pivx.conf getblockchaininfo
# Watch "blocks" climb toward the current fleet height
```

---

## Step 9 — Register masternode (if applicable)

If this is a masternode host, follow the masternode registration process at
`docs/LIFECYCLE.md#phase-5-masternode--quorum-testing`.

Generate BLS keypair on the new instance:
```bash
ssh root@<new-host-ip>
pivx-cli -conf=/etc/pivx/tn6-cb16-mn1/pivx.conf generateblskeypair
```

Fill `bls_operator_key` with the `secret` output.
Set `masternode_enabled: true` in host_vars after ProRegTx is confirmed.
Then:
```bash
make deploy-pivx LIMIT=tn6-cb16
make enable-masternodes
```

---

## Removing a Host

To remove a host from the fleet:

1. Stop all instances on the host:
   ```bash
   make cohort-stop COHORT=<cohort> LIMIT=<hostname>
   # Or stop individual services:
   ansible <hostname> -i ansible/inventories/testnet6 -m systemd \
     -a "name=pivxd@<instance> state=stopped" --become
   ```

2. Remove the host from `hosts.yml` (delete all group entries).

3. Delete `host_vars/<hostname>.yml`.

4. If it was a Tor host, the onion address is now gone. Other nodes that
   connected to it via onion will age out the connection naturally.

5. If it was a masternode, the DMN will be marked `POSE_BANNED` after
   missing enough quorum commitments. You may want to revoke the ProRegTx:
   ```
   protx revoke <dmn-proTxHash> <operatorKey>
   ```
