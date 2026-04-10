# Runbook: Upgrade PIVX Binary

## When to use this

- A new testnet6-compatible PIVX build is available
- Directed by the core team to upgrade to a specific commit/release

---

## Pre-upgrade checklist

- [ ] Confirm the new binary tag and SHA256 from the PIVX GitHub release page
- [ ] Test the binary locally if practical: `./pivxd --version`
- [ ] Announce the upgrade window in team chat
- [ ] Optional: snapshot VPS disks at the provider level for rollback

---

## Steps

### 1. Update group_vars

Edit `ansible/inventories/testnet6/group_vars/all/main.yml`:

```yaml
pivx_version: "X.Y.Z"
pivx_archive_url: "https://github.com/PIVX-Project/PIVX/releases/download/vX.Y.Z/pivx-X.Y.Z-x86_64-linux-gnu.tar.gz"
pivx_checksum: "sha256:<real-sha256>"
```

Commit these changes to version control.

### 2. Run upgrade

```bash
make upgrade-pivx
```

This rolls 3 hosts at a time:
1. Stops all PIVX instances on the batch
2. Downloads and installs the new binary
3. Starts all instances
4. Waits for RPC to respond
5. Moves to the next batch

### 3. Verify

```bash
make status
```

Check Grafana dashboards for any unhealthy nodes.

Quick per-instance check:
```bash
pivx-cli -conf=/etc/pivx/<instance>/pivx.conf \
         -datadir=/var/lib/pivx/<instance> \
         getblockchaininfo | jq '{"version":.version,"blocks":.blocks}'
```

### 4. Rollback (if needed)

The old binary is still in `/opt/pivx/<old-version>/`. To roll back:

1. Revert `pivx_version` and related vars in group_vars
2. `make upgrade-pivx`

Or manually per-host (symlink rollback):
```bash
# The old release is preserved at /opt/pivx/releases/<old-version>/
ln -sfn /opt/pivx/releases/<old-version> /opt/pivx/current
systemctl restart 'pivxd@*.service'
```

---

## Binary install layout

The `pivx_install` role uses a versioned layout:
```
/opt/pivx/
  releases/
    5.6.1/          ← old version (kept for rollback)
    5.7.0/          ← current version
      bin/
        pivxd
        pivx-cli
        pivx-tx
        sapling-fetch-params
  current -> releases/5.7.0   ← symlink updated by role
```

All systemd units use `/opt/pivx/current/bin/pivxd` — so updating the symlink
is all that's needed for an in-place version switch.

---

## Notes

- Old releases remain in `/opt/pivx/releases/`. Clean up after successful upgrade:
  ```bash
  ansible all -i ansible/inventories/testnet6 \
    -m shell -a "ls /opt/pivx/releases/" --become
  # Remove old version when confident:
  ansible all -i ansible/inventories/testnet6 \
    -m file -a "path=/opt/pivx/releases/<old-version> state=absent" --become
  ```
- Log the upgrade in a git commit message for traceability.
- Confirm `nFirstPoSBlock` has not changed in the new version's chainparams.cpp.
