# PIVX Testnet6 — Inventory Schema Examples

This directory contains example `host_vars` files showing the full supported
variable schema for each host type. Use these as copy-paste starting points.

## Files

| File | Host type |
|------|-----------|
| `example_masternode_host.yml` | Contabo host running 6 masternode instances |
| `example_seed_host.yml` | Seeder/bootstrap-miner instance schema |
| `example_infra_host.yml` | Monitoring / observer host |

## Schema quick reference

Each host has a `pivx_instances` list. Every item in that list defines one
`pivxd` process and systemd unit (`pivxd@<name>.service`).

```yaml
pivx_instances:
  - name: <string>          # Used as systemd instance name and in all labels
    enabled: <bool>         # If false, service will be stopped/disabled
    slot: <int>             # 0-based position on this host (affects default ports)
    protocol_class: ipv4|ipv6|tor
    cohort: ipv4|ipv6|tor   # Chaos targeting group
    role: masternode|seeder|observer|miner
    bind_addr: <ip>         # Local bind address for pivxd
    external_ip: <ip>       # Advertised IP (what peers connect to)
    p2p_port: <int>
    rpc_port: <int>
    rpc_user: <string>
    rpc_password: <string>  # Set via vault or host_vars; never hardcode real value
    datadir: <path>
    logdir: <path>
    confdir: <path>
    mining_enabled: <bool>  # Phase 2 only: enable CPU mining
    staking_enabled: <bool> # Phase 3+: enable staking
    masternode_enabled: <bool> # Phase 4: enable masternode mode
    bls_operator_key: <string> # BLS secret key — from 'pivx-cli bls generate'
    onion_address: <string>    # tor only: populated after first deploy-tor run
    onion_service_dir: <path>  # tor only: /var/lib/tor/<service-name>/
    extra_conf: |           # Raw pivx.conf lines appended verbatim
      # custom settings here
```
