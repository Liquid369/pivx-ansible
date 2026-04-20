#!/usr/bin/env python3
"""
Generate host_vars stub files for the Testnet6 inventory.

Topology:
  - 8 Contabo MN hosts  (tn6-cb1 .. tn6-cb8)
  - 5 KS-5 MN hosts     (tn6-rbx1, tn6-sbg1, tn6-gra1, tn6-bhs1, tn6-sgp1)
  - 2 KS-1 seed hosts   (tn6-ks-seed01, tn6-ks-seed02)

Each MN host runs 6 instances (per-host local numbering, slots 0-5):
  Slot 0  v4-mn01   IPv4 #1   P2P 51474  RPC 51478
  Slot 1  v4-mn02   IPv4 #2   P2P 51484  RPC 51488
  Slot 2  v6-mn03   IPv6 #1   P2P 51494  RPC 51498
  Slot 3  v6-mn04   IPv6 #2   P2P 51504  RPC 51508
  Slot 4  tor-mn05  Tor  #1   P2P 51514  RPC 51518
  Slot 5  tor-mn06  Tor  #2   P2P 51524  RPC 51528

Run from repo root:
  python3 scripts/generate_stub_host_vars.py [--force]

Without --force, existing files are NOT overwritten.
"""
import os
import sys

BASE = os.path.join(os.path.dirname(__file__), "..", "ansible", "inventories", "testnet6", "host_vars")
FORCE = "--force" in sys.argv

# ---------------------------------------------------------------------------
# Topology data
# ---------------------------------------------------------------------------

# (hostname, provider, chaos_group, ipv4_1, ipv4_2, ipv6_1, ipv6_2)
# IPs are RFC 5737 / RFC 3849 documentation-range placeholders.
CONTABO_HOSTS = [
    ("tn6-cb1", "contabo", "chaos_contabo",
     "203.0.113.11", "203.0.113.111", "2001:db8:cb::11", "2001:db8:cb::12"),
    ("tn6-cb2", "contabo", "chaos_contabo",
     "203.0.113.12", "203.0.113.112", "2001:db8:cb::21", "2001:db8:cb::22"),
    ("tn6-cb3", "contabo", "chaos_contabo",
     "203.0.113.13", "203.0.113.113", "2001:db8:cb::31", "2001:db8:cb::32"),
    ("tn6-cb4", "contabo", "chaos_contabo",
     "203.0.113.14", "203.0.113.114", "2001:db8:cb::41", "2001:db8:cb::42"),
    ("tn6-cb5", "contabo", "chaos_contabo",
     "203.0.113.15", "203.0.113.115", "2001:db8:cb::51", "2001:db8:cb::52"),
    ("tn6-cb6", "contabo", "chaos_contabo",
     "203.0.113.16", "203.0.113.116", "2001:db8:cb::61", "2001:db8:cb::62"),
    ("tn6-cb7", "contabo", "chaos_contabo",
     "203.0.113.17", "203.0.113.117", "2001:db8:cb::71", "2001:db8:cb::72"),
    ("tn6-cb8", "contabo", "chaos_contabo",
     "203.0.113.18", "203.0.113.118", "2001:db8:cb::81", "2001:db8:cb::82"),
]

# (hostname, provider, chaos_group, region_label, location,
#  ipv4_1, ipv4_2, ipv6_1, ipv6_2)
KS_HOSTS = [
    ("tn6-rbx1", "kimsufi", "chaos_kimsufi", "rbx", "Roubaix, France (KS-5)",
     "203.0.113.21", "203.0.113.121", "2001:db8:ks::21", "2001:db8:ks::22"),
    ("tn6-sbg1", "kimsufi", "chaos_kimsufi", "sbg", "Strasbourg, France (KS-5)",
     "203.0.113.22", "203.0.113.122", "2001:db8:ks::31", "2001:db8:ks::32"),
    ("tn6-gra1", "kimsufi", "chaos_kimsufi", "gra", "Gravelines, France (KS-5)",
     "203.0.113.23", "203.0.113.123", "2001:db8:ks::41", "2001:db8:ks::42"),
    ("tn6-bhs1", "kimsufi", "chaos_kimsufi", "bhs", "Beauharnois, Canada (KS-5)",
     "203.0.113.24", "203.0.113.124", "2001:db8:ks::51", "2001:db8:ks::52"),
    ("tn6-sgp1", "kimsufi", "chaos_kimsufi", "sgp", "Singapore (KS-5)",
     "203.0.113.25", "203.0.113.125", "2001:db8:ks::61", "2001:db8:ks::62"),
]

# (hostname, provider, chaos_group, location, ipv4, ipv6)
SEED_HOSTS = [
    ("tn6-ks-seed01", "kimsufi", "chaos_kimsufi", "KS-1 (region TBD)",
     "203.0.113.31", "2001:db8:ks::71"),
    ("tn6-ks-seed02", "kimsufi", "chaos_kimsufi", "KS-1 (region TBD)",
     "203.0.113.32", "2001:db8:ks::81"),
]

# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

_PROTO = {"v4": "ipv4", "v6": "ipv6", "tor": "tor"}


def mn_instance(host, slot, itype, mn_num,
                bind_expr, external_expr, extra_conf_lines,
                onion_service=False):
    """Return a single pivx_instance block (YAML fragment, 2-space indent)."""
    p2p = 51474 + slot * 10
    rpc  = 51478 + slot * 10
    name = f"{host}-{itype}-mn{mn_num:02d}"
    protocol_class = _PROTO.get(itype, itype)
    rpc_user = f"rpc_{itype}mn{mn_num:02d}"

    lines = [
        f"  - name: {name}",
        f"    enabled: true",
        f"    slot: {slot}",
        f"    protocol_class: {protocol_class}",
        f"    cohort: {protocol_class}",
        f"    role: masternode",
        f"    bind_addr: \"{bind_expr}\"",
        f"    external_ip: \"{external_expr}\"",
    ]
    if onion_service:
        lines += [
            f"    onion_address: \"\"          # FILL IN after: cat /var/lib/tor/pivx_hs/{name}/hostname",
            f"    onion_service_dir: \"/var/lib/tor/pivx_hs/{name}\"",
        ]
    lines += [
        f"    p2p_port: {p2p}",
        f"    rpc_port: {rpc}",
        f"    rpc_user: {rpc_user}",
        f"    rpc_password: \"{{{{ vault_pivx_rpc_password }}}}\"",
        f"    datadir: \"/var/lib/pivx/{name}\"",
        f"    logdir: \"/var/log/pivx/{name}\"",
        f"    confdir: \"/etc/pivx/{name}\"",
        f"    mining_enabled: false",
        f"    staking_enabled: false       # set true in Phase 3 once coins arrive",
        f"    masternode_enabled: false    # set true in Phase 4 after DMN registration",
        f"    bls_operator_key: \"REPLACE_ME\"",
    ]
    if extra_conf_lines:
        lines.append(f"    extra_conf:")
        for ec in extra_conf_lines:
            lines.append(f"      - \"{ec}\"")
    else:
        lines.append(f"    extra_conf: []")
    return "\n".join(lines)


def write_mn_host(host, provider, chaos_group, ipv4_1, ipv4_2, ipv6_1, ipv6_2,
                  location="", is_ks=False):
    loc_comment = f"  — {location}" if location else ""
    content = f"""\
# host_vars/{host}.yml{loc_comment}
#
# 6 PIVX masternode instances per host:
#   Slot 0  v4-mn01   IPv4 #1   P2P 51474 / RPC 51478
#   Slot 1  v4-mn02   IPv4 #2   P2P 51484 / RPC 51488
#   Slot 2  v6-mn03   IPv6 #1   P2P 51494 / RPC 51498
#   Slot 3  v6-mn04   IPv6 #2   P2P 51504 / RPC 51508
#   Slot 4  tor-mn05  Tor  #1   P2P 51514 / RPC 51518
#   Slot 5  tor-mn06  Tor  #2   P2P 51524 / RPC 51528
#
# IMPORTANT: Replace ALL REPLACE_ME / RFC 5737 / RFC 3849 placeholder values.

provider: {provider}
chaos_group: {chaos_group}
host_label: {host}

host_ipv4:   "{ipv4_1}"    # REPLACE_ME
host_ipv4_2: "{ipv4_2}"    # REPLACE_ME  (second public IPv4 / failover IP)
host_ipv6:   "{ipv6_1}"    # REPLACE_ME
host_ipv6_2: "{ipv6_2}"    # REPLACE_ME  (second IPv6 from /56 or /64 allocation)

pivx_instances:

"""
    instances = [
        mn_instance(host, 0, "v4", 1,
                    "{{ host_ipv4 }}", "{{ host_ipv4 }}", []),
        mn_instance(host, 1, "v4", 2,
                    "{{ host_ipv4_2 }}", "{{ host_ipv4_2 }}", []),
        mn_instance(host, 2, "v6", 3,
                    "[{{ host_ipv6 }}]", "{{ host_ipv6 }}",
                    ["ipv4=0", "ipv6=1"]),
        mn_instance(host, 3, "v6", 4,
                    "[{{ host_ipv6_2 }}]", "{{ host_ipv6_2 }}",
                    ["ipv4=0", "ipv6=1"]),
        mn_instance(host, 4, "tor", 5,
                    "127.0.0.1", "",
                    ["onlynet=onion", "proxy=127.0.0.1:9050", "listen=1"],
                    onion_service=True),
        mn_instance(host, 5, "tor", 6,
                    "127.0.0.1", "",
                    ["onlynet=onion", "proxy=127.0.0.1:9050", "listen=1"],
                    onion_service=True),
    ]
    content += "\n\n".join(instances) + "\n"
    return content


def write_seed_host(host, provider, chaos_group, location, ipv4, ipv6):
    return f"""\
# host_vars/{host}.yml  — {location}
#
# KS-1 seed/bootstrap node and Phase 2 bootstrap miner.
# This host is in both `seeders` and `bootstrap_miners` inventory groups.
#
# LIFECYCLE ROLE:
#   Phase 2: seed + bootstrap miner  (mining_enabled=true)
#   Phase 3+: seed-only              (run `make stop-bootstrap-mining` to flip)
#
# IMPORTANT: Replace all REPLACE_ME / placeholder values before first deploy.

provider: {provider}
chaos_group: {chaos_group}
host_label: {host}

host_ipv4: "{ipv4}"    # REPLACE_ME
host_ipv6: "{ipv6}"    # REPLACE_ME  (optional; fill in if KS-1 has IPv6)

# Mining reward address for Phase 2.
# Generate with: pivx-cli -testnet getnewaddress "" bech32
bootstrap_mining_address: "REPLACE_ME"

pivx_instances:

  - name: {host}
    enabled: true
    slot: 0
    protocol_class: ipv4
    cohort: ipv4
    role: seeder
    bind_addr: "{{{{ host_ipv4 }}}}"
    external_ip: "{{{{ host_ipv4 }}}}"
    p2p_port: 51474
    rpc_port: 51478
    rpc_user: rpc_{host.replace('-', '_')}
    rpc_password: "{{{{ vault_pivx_rpc_password }}}}"
    datadir: "/var/lib/pivx/{host}"
    logdir: "/var/log/pivx/{host}"
    confdir: "/etc/pivx/{host}"
    mining_enabled: true         # Phase 2: mine to bootstrap chain
    staking_enabled: false       # flip true in Phase 3
    masternode_enabled: false    # seeders are not masternodes
    bls_operator_key: ""
    extra_conf:
      - "maxconnections=256"
      - "listen=1"
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def write_file(path, content):
    if os.path.exists(path) and not FORCE:
        print(f"SKIP  {path}  (exists; use --force to overwrite)")
        return
    with open(path, "w") as f:
        f.write(content)
    print(f"WROTE {path}")


def main():
    os.makedirs(BASE, exist_ok=True)

    for host, provider, chaos_group, ipv4_1, ipv4_2, ipv6_1, ipv6_2 in CONTABO_HOSTS:
        path = os.path.join(BASE, f"{host}.yml")
        write_file(path, write_mn_host(host, provider, chaos_group,
                                       ipv4_1, ipv4_2, ipv6_1, ipv6_2))

    for host, provider, chaos_group, region, location, ipv4_1, ipv4_2, ipv6_1, ipv6_2 in KS_HOSTS:
        path = os.path.join(BASE, f"{host}.yml")
        write_file(path, write_mn_host(host, provider, chaos_group,
                                       ipv4_1, ipv4_2, ipv6_1, ipv6_2,
                                       location=location, is_ks=True))

    for host, provider, chaos_group, location, ipv4, ipv6 in SEED_HOSTS:
        path = os.path.join(BASE, f"{host}.yml")
        write_file(path, write_seed_host(host, provider, chaos_group,
                                         location, ipv4, ipv6))

    print("Done.")


if __name__ == "__main__":
    main()
