# Runbook: Migrate to v6.0 Feature Tests

**When to use**: After the fresh Testnet6 chain has stable seed connectivity,
active staking, registered masternodes, and healthy quorum formation.

The goal is to separate base-network bring-up problems from new v6.0 behavior.
First make the network boring and observable, then upgrade into the feature set
you actually want to test.

---

## Preconditions

- [ ] `make status` shows all expected seed, staking, masternode, and observer
      instances running.
- [ ] `make verify-readiness` is healthy for the current lifecycle phase.
- [ ] Staking wallets are producing PoS blocks.
- [ ] The intended masternode cohort is registered and enabled.
- [ ] `listquorums` and `quorumdkgstatus` show expected quorum activity.
- [ ] The v6.0 test binary URL and SHA256 are known.
- [ ] Any changed chain parameters or activation heights are written down.
- [ ] Provider snapshots or another rollback route exist for risky builds.

---

## Procedure

### 1. Record the baseline

```bash
make status
make verify-readiness
make collect-debug
```

Keep this bundle as the known-good pre-upgrade state.

### 2. Update binary settings

Edit `ansible/inventories/testnet6/group_vars/all/main.yml`:

```yaml
pivx_version: "6.0.0-test"
pivx_archive_url: "<artifact-url>"
pivx_checksum: "sha256:<real-sha256>"
```

Commit that configuration change before upgrading so the exact artifact is
traceable.

### 3. Roll the fleet

```bash
make upgrade-pivx PIVX_VERSION=6.0.0-test
```

The upgrade playbook rolls hosts in batches, restarts their PIVX instances, and
waits for RPC to return before continuing.

### 4. Verify chain and quorum health

```bash
make status
make verify-readiness
```

Spot-check from an observer or a known-good node:

```bash
pivx-cli -conf=/etc/pivx/tn6-obs01/pivx.conf getblockchaininfo
pivx-cli -conf=/etc/pivx/tn6-obs01/pivx.conf getstakingstatus
pivx-cli -conf=/etc/pivx/tn6-obs01/pivx.conf listquorums
pivx-cli -conf=/etc/pivx/tn6-obs01/pivx.conf quorumdkgstatus
```

### 5. Run feature-specific tests

Run the new staking and masternode architecture test cases only after the
upgrade baseline is clean. Capture logs after each test group:

```bash
make collect-debug
```

---

## Rollback

If the upgraded fleet stalls or diverges:

1. Collect a debug bundle before changing anything:
   ```bash
   make collect-debug
   ```
2. Revert `pivx_version`, `pivx_archive_url`, and `pivx_checksum` to the prior
   known-good build.
3. Roll back with:
   ```bash
   make upgrade-pivx PIVX_VERSION=<previous-version>
   ```
4. If the chain data itself is corrupted or incompatible, restore provider
   snapshots or wipe the chain and restart from bootstrap mining.

