# Inventory Model — Schema Reference

This document describes the data model used to represent hosts and PIVX instances
in the Ansible inventory.

---

## Host Variables (host_vars/<hostname>.yml)

Every host has these top-level variables:

| Variable       | Type   | Required | Description |
|----------------|--------|----------|-------------|
| `provider`     | string | yes      | `contabo` now; `ovh` later — must match a `provider_*` group |
| `provider_plan`| string | rec      | Contabo plan class such as `contabo_4vcpu` or `contabo_6vcpu` |
| `chaos_group`  | string | yes      | `chaos_contabo` now; `chaos_ovh` later |
| `host_label`   | string | yes      | Short human name used in logs and hostnames |
| `host_ipv4`    | string | yes      | Primary public IPv4 (RFC 5737 placeholder until real IP) |
| `host_ipv6`    | string | cond     | Public IPv6; required when any instance is `protocol_class: ipv6` |
| `pivx_instances` | list | yes    | List of PIVX instance dicts (see below) |

---

## Instance Schema (pivx_instances[])

Each entry in `pivx_instances` defines one independent PIVX daemon.

```yaml
pivx_instances:
  - name: tn6-cb1-v4-mn01      # Unique across the entire fleet
    enabled: true              # false = skip deploy/start for this instance
    slot: 0                    # 0-based; used to compute port offsets
    protocol_class: ipv4       # ipv4 | ipv6 | tor
    cohort: ipv4               # Same as protocol_class; the Ansible/Loki label
    role: masternode           # masternode | seeder | observer
    bind_addr: "192.0.2.11"    # bind= value in pivx.conf; bracket IPv6 if needed
    external_ip: "192.0.2.11"  # externalip= value; omit for Tor instances
    p2p_port: 51474            # pivx_p2p_port_base + slot*10
    rpc_port: 51478            # pivx_rpc_port_base + slot*10
    rpc_user: rpc_v4mn01       # Unique RPC username per instance
    rpc_password: "{{ vault_pivx_rpc_password }}"
    datadir: /var/lib/pivx/tn6-cb1-v4-mn01
    logdir:  /var/log/pivx/tn6-cb1-v4-mn01
    confdir: /etc/pivx/tn6-cb1-v4-mn01
    bls_operator_key: "REPLACE_ME"   # BLS operator privkey from DMN registration
    extra_conf: []             # Additional pivx.conf lines; freeform YAML list
```

### Tor extension fields

Tor instances add:

```yaml
    bind_addr: "127.0.0.1"          # Tor binds locally only
    external_ip: ""                 # Left blank; filled after HS creation
    onion_service_dir: /var/lib/tor/pivx_hs/tn6-cb1-tor-mn05
```

### Seeder / Observer differences

- **seeder**: `bls_operator_key: ""` — not a masternode
- **observer**: `bls_operator_key: ""` + `extra_conf: ["txindex=1"]`

---

## Inventory Groups

| Group               | Membership | Purpose |
|---------------------|------------|---------|
| `masternodes`       | 15 hosts   | Contabo hosts with masternode instances |
| `seeders`           | 3 hosts    | Colocated bootstrap/seed instances on `tn6-cb1..tn6-cb3` |
| `observers`         | 1 host     | Observer PIVX node |
| `monitoring`        | 1 host     | Monitoring stack (shared with observer) |
| `provider_contabo`  | 16 hosts   | 15 Contabo lab hosts + infra |
| `provider_ovh`      | 0 active   | Future OVH/Kimsufi KS-A expansion group |
| `cohort_ipv4`       | masternodes + seeders | Hosts with IPv4 instances |
| `cohort_ipv6`       | masternodes | Hosts with IPv6 instances |
| `cohort_tor`        | masternodes | Hosts with Tor instances |
| `chaos_contabo`     | = provider_contabo | Chaos targeting alias |
| `chaos_ovh`         | = provider_ovh | Chaos targeting alias |

---

## Port Allocation Summary

The active masternode layout uses six slots per host:

| Slot | Protocol / Role | P2P   | RPC   |
|------|------------------|-------|-------|
| 0    | IPv4 MN #1       | 51474 | 51478 |
| 1    | IPv4 MN #2       | 51484 | 51488 |
| 2    | IPv6 MN #1       | 51494 | 51498 |
| 3    | IPv6 MN #2       | 51504 | 51508 |
| 4    | Tor MN #1        | 51514 | 51518 |
| 5    | Tor MN #2        | 51524 | 51528 |
| 6    | Seeder           | 51534 | 51538 |

Slot 6 exists only on `tn6-cb1..tn6-cb3`.

Ports are per-host. The same port numbers are used on every masternode host
because they bind to distinct IPs, IPv6 addresses, localhost for Tor, or unique
ports.

---

## Extending the Model

### Add a new host

1. Add to `hosts.yml` under the appropriate parent groups.
2. Create `host_vars/<hostname>.yml` using `tn6-cb1.yml` as the template.
3. Assign unique instance names and sequence numbers.
4. Run `make check-inventory` to validate.

### Add an instance to an existing host

1. Add a new entry to `pivx_instances` in `host_vars/<hostname>.yml`.
2. Choose a new slot number and compute port offsets.
3. Ensure the instance name is globally unique.
4. Run `make deploy-pivx --limit <hostname>`.

### Remove an instance

1. Set `enabled: false` on the instance entry.
2. Run `make deploy-pivx --limit <hostname>` to stop and disable the unit.
3. Optionally remove the entry entirely and clean up datadirs manually.

---

## Validation

Run `make check-inventory` which calls `scripts/validate_inventory.py`.
It checks:
- All instance names are globally unique
- Ports don't conflict within a host
- Required fields are present
- `bls_operator_key` is not `REPLACE_ME` when `masternode_enabled == true`
