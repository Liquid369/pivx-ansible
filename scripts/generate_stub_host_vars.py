#!/usr/bin/env python3
"""
Generate host_vars stub files for the active Testnet6 inventory.

Current topology:
  - 15 Contabo masternode hosts (tn6-cb1 .. tn6-cb15)
  - tn6-cb1 .. tn6-cb7 are the smaller 4 vCPU class
  - tn6-cb8 .. tn6-cb15 are the larger 6 vCPU class
  - tn6-cb1 .. tn6-cb3 also run one colocated seeder/bootstrap-miner instance
  - tn6-infra01 remains a monitoring/observer host and is maintained manually

Each masternode host runs 6 masternode instances:
  Slot 0  v4-mn01   IPv4 #1   P2P 51474  RPC 51478
  Slot 1  v4-mn02   IPv4 #2   P2P 51484  RPC 51488
  Slot 2  v6-mn03   IPv6 #1   P2P 51494  RPC 51498
  Slot 3  v6-mn04   IPv6 #2   P2P 51504  RPC 51508
  Slot 4  tor-mn05  Tor  #1   P2P 51514  RPC 51518
  Slot 5  tor-mn06  Tor  #2   P2P 51524  RPC 51528

Seeder/bootstrap hosts add:
  Slot 6  seed01/2/3 IPv4     P2P 51534  RPC 51538

Run from repo root:
  python3 scripts/generate_stub_host_vars.py [--force]

Without --force, existing files are NOT overwritten.
"""
import os
import sys

BASE = os.path.join(os.path.dirname(__file__), "..", "ansible", "inventories", "testnet6", "host_vars")
FORCE = "--force" in sys.argv

P2P_BASE = 51474
RPC_BASE = 51478

_PROTO = {"v4": "ipv4", "v6": "ipv6", "tor": "tor"}


def contabo_hosts():
    hosts = []
    for idx in range(1, 16):
        plan = "contabo_4vcpu" if idx <= 7 else "contabo_6vcpu"
        hosts.append({
            "host": f"tn6-cb{idx}",
            "plan": plan,
            "ipv4_1": f"203.0.113.{10 + idx}",
            "ipv4_2": f"203.0.113.{110 + idx}",
            "ipv6_1": f"2001:db8:cb::{idx}1",
            "ipv6_2": f"2001:db8:cb::{idx}2",
            "seed_index": idx if idx <= 3 else None,
        })
    return hosts


def port_for(slot, base):
    return base + slot * 10


def mn_instance(host, slot, itype, mn_num, bind_expr, external_expr, extra_conf_lines, onion_service=False):
    name = f"{host}-{itype}-mn{mn_num:02d}"
    protocol_class = _PROTO.get(itype, itype)
    rpc_user = f"rpc_{itype}mn{mn_num:02d}"

    lines = [
        f"  - name: {name}",
        "    enabled: true",
        f"    slot: {slot}",
        f"    protocol_class: {protocol_class}",
        f"    cohort: {protocol_class}",
        "    role: masternode",
        f"    bind_addr: \"{bind_expr}\"",
        f"    external_ip: \"{external_expr}\"",
    ]
    if onion_service:
        lines += [
            f"    onion_address: \"\"          # FILL IN after: cat /var/lib/tor/pivx_hs/{name}/hostname",
            f"    onion_service_dir: \"/var/lib/tor/pivx_hs/{name}\"",
        ]
    lines += [
        f"    p2p_port: {port_for(slot, P2P_BASE)}",
        f"    rpc_port: {port_for(slot, RPC_BASE)}",
        f"    rpc_user: {rpc_user}",
        "    rpc_password: \"{{ vault_pivx_rpc_password }}\"",
        f"    datadir: \"/var/lib/pivx/{name}\"",
        f"    logdir: \"/var/log/pivx/{name}\"",
        f"    confdir: \"/etc/pivx/{name}\"",
        "    mining_enabled: false",
        "    staking_enabled: false       # set true in Phase 3 once coins arrive",
        "    masternode_enabled: false    # set true in Phase 4 after DMN registration",
        "    bls_operator_key: \"REPLACE_ME\"",
    ]
    if extra_conf_lines:
        lines.append("    extra_conf:")
        for ec in extra_conf_lines:
            lines.append(f"      - \"{ec}\"")
    else:
        lines.append("    extra_conf: []")
    return "\n".join(lines)


def seeder_instance(host, seed_index):
    name = f"{host}-seed{seed_index:02d}"
    slot = 6
    return "\n".join([
        f"  - name: {name}",
        "    enabled: true",
        f"    slot: {slot}",
        "    protocol_class: ipv4",
        "    cohort: ipv4",
        "    role: seeder",
        "    bind_addr: \"{{ host_ipv4 }}\"",
        "    external_ip: \"{{ host_ipv4 }}\"",
        f"    p2p_port: {port_for(slot, P2P_BASE)}",
        f"    rpc_port: {port_for(slot, RPC_BASE)}",
        f"    rpc_user: rpc_seed{seed_index:02d}",
        "    rpc_password: \"{{ vault_pivx_rpc_password }}\"",
        f"    datadir: \"/var/lib/pivx/{name}\"",
        f"    logdir: \"/var/log/pivx/{name}\"",
        f"    confdir: \"/etc/pivx/{name}\"",
        "    mining_enabled: true         # Phase 2: mine to bootstrap chain",
        "    staking_enabled: false       # can be flipped true in Phase 3",
        "    masternode_enabled: false    # seeders are bootstrap peers, not DMNs",
        "    bls_operator_key: \"\"",
        "    extra_conf:",
        "      - \"maxconnections=256\"",
        "      - \"listen=1\"",
        "      - \"dnsseed=0\"",
        "      - \"listenonion=0\"",
    ])


def write_mn_host(meta):
    host = meta["host"]
    seed_index = meta["seed_index"]
    expected = 7 if seed_index else 6
    role_label = "mixed_masternode_seeder" if seed_index else "masternode"
    seed_note = "\n# This host also runs a seeder/bootstrap-miner instance in slot 6." if seed_index else ""

    content = f"""\
# host_vars/{host}.yml
#
# Active Contabo host for PIVX Testnet6.
# Plan class: {meta["plan"]}
# 6 PIVX masternode instances per host:
#   Slot 0  v4-mn01   IPv4 #1   P2P 51474 / RPC 51478
#   Slot 1  v4-mn02   IPv4 #2   P2P 51484 / RPC 51488
#   Slot 2  v6-mn03   IPv6 #1   P2P 51494 / RPC 51498
#   Slot 3  v6-mn04   IPv6 #2   P2P 51504 / RPC 51508
#   Slot 4  tor-mn05  Tor  #1   P2P 51514 / RPC 51518
#   Slot 5  tor-mn06  Tor  #2   P2P 51524 / RPC 51528{seed_note}
#
# IMPORTANT: Replace ALL REPLACE_ME / RFC 5737 / RFC 3849 placeholder values.

provider: contabo
provider_plan: {meta["plan"]}
chaos_group: chaos_contabo
node_role: {role_label}
host_label: {host}
pivx_instances_expected: {expected}

host_ipv4:   "{meta["ipv4_1"]}"    # REPLACE_ME
host_ipv4_2: "{meta["ipv4_2"]}"    # REPLACE_ME  (second public IPv4 / failover IP)
host_ipv6:   "{meta["ipv6_1"]}"    # REPLACE_ME
host_ipv6_2: "{meta["ipv6_2"]}"    # REPLACE_ME  (second IPv6 from /56 or /64 allocation)
"""
    if seed_index:
        content += """
# Mining reward address for the colocated bootstrap seeder.
# Generate with: pivx-cli -testnet getnewaddress "" bech32
bootstrap_mining_address: "REPLACE_ME"
"""
    content += """
# Firewall: open all PIVX P2P slots used by this host.
ufw_pivx_ports:
  - "{{ pivx_p2p_port_base }}"
  - "{{ pivx_p2p_port_base + 10 }}"
  - "{{ pivx_p2p_port_base + 20 }}"
  - "{{ pivx_p2p_port_base + 30 }}"
  - "{{ pivx_p2p_port_base + 40 }}"
  - "{{ pivx_p2p_port_base + 50 }}"
"""
    if seed_index:
        content += "  - \"{{ pivx_p2p_port_base + 60 }}\"\n"

    content += "\npivx_instances:\n\n"
    instances = [
        mn_instance(host, 0, "v4", 1, "{{ host_ipv4 }}", "{{ host_ipv4 }}", []),
        mn_instance(host, 1, "v4", 2, "{{ host_ipv4_2 }}", "{{ host_ipv4_2 }}", []),
        mn_instance(host, 2, "v6", 3, "[{{ host_ipv6 }}]", "{{ host_ipv6 }}", ["ipv4=0", "ipv6=1"]),
        mn_instance(host, 3, "v6", 4, "[{{ host_ipv6_2 }}]", "{{ host_ipv6_2 }}", ["ipv4=0", "ipv6=1"]),
        mn_instance(host, 4, "tor", 5, "127.0.0.1", "", ["onlynet=onion", "proxy=127.0.0.1:9050", "listen=1"], onion_service=True),
        mn_instance(host, 5, "tor", 6, "127.0.0.1", "", ["onlynet=onion", "proxy=127.0.0.1:9050", "listen=1"], onion_service=True),
    ]
    if seed_index:
        instances.append(seeder_instance(host, seed_index))
    content += "\n\n".join(instances) + "\n"
    return content


def write_file(path, content):
    if os.path.exists(path) and not FORCE:
        print(f"SKIP  {path}  (exists; use --force to overwrite)")
        return
    with open(path, "w") as f:
        f.write(content)
    print(f"WROTE {path}")


def main():
    os.makedirs(BASE, exist_ok=True)
    for meta in contabo_hosts():
        write_file(os.path.join(BASE, f"{meta['host']}.yml"), write_mn_host(meta))
    print("Done.")


if __name__ == "__main__":
    main()
