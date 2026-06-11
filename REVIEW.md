# Testnet6 Ansible — Current Review

> Updated for the active Contabo-first topology.

## Active Topology

| Category | Current state |
|---|---|
| Active providers | Contabo only |
| Masternode servers | 15 total: `tn6-cb1..tn6-cb15` |
| Contabo plan split | `tn6-cb1..cb7` = 4 vCPU class; `tn6-cb8..cb15` = 6 vCPU class |
| Masternode instances | 90 total: 30 IPv4, 30 IPv6, 30 Tor |
| Seed/bootstrap instances | 3 colocated: `tn6-cb1-seed01`, `tn6-cb2-seed02`, `tn6-cb3-seed03` |
| Observer/monitoring | `tn6-infra01` |
| Future expansion | OVH/Kimsufi KS-A, likely 10-12 hosts first, ideally 15 |

## Files To Review First

1. `ansible/inventories/testnet6/hosts.yml`
2. `ansible/inventories/testnet6/host_vars/tn6-cb1.yml`
3. `ansible/inventories/testnet6/group_vars/all/main.yml`
4. `ansible/roles/pivx_instance/templates/pivx.conf.j2`
5. `docs/QUICKSTART.md`

## Blocking Before First Real Deploy

- Replace all placeholder `203.0.113.x` and `2001:db8:*` addresses.
- Populate `ansible/inventories/testnet6/group_vars/all/vault.yml` from the example and encrypt it.
- Set real `pivx_checksum` before downloading release binaries.
- Confirm Testnet6 values when they are available: network magic, PoS activation height, LLMQ type, quorum size.
- Fill BLS operator keys and set `masternode_enabled: true` only after DMN registration is ready.

## Known Intentional Placeholders

`pivx_version` currently remains `5.6.1` because v6.0 is not official yet. This
can be changed to `5.6.2` or a v6.0 test binary when you decide which build to
test.

## Verification Commands

```bash
make check-inventory
make show-layout
ansible-playbook -i ansible/inventories/testnet6 ansible/playbooks/site.yml --syntax-check
```

## Notes

`tc/netem` chaos is host-interface scoped. On mixed-protocol hosts it affects
all traffic on targeted hosts. Use `cohort-stop`, `cohort-start`, and
`cohort-restart` for precise protocol-cohort failure simulation.
