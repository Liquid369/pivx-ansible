#!/usr/bin/env python3
"""
Generate stub host_vars files for remaining masternode hosts.
Run once from repo root: python3 scripts/generate_stub_host_vars.py

This will NOT overwrite existing files.
"""
import os

BASE = os.path.join(os.path.dirname(__file__), "..", "ansible", "inventories", "testnet6", "host_vars")

HOSTS = [
    # (hostname, provider, chaos_group, ipv4_last_octet, ipv6_suffix, mn_start_index)
    ("tn6-cb2",  "contabo", "chaos_contabo", "203.0.113.12", "2001:db8:cb::12",  4),
    ("tn6-cb3",  "contabo", "chaos_contabo", "203.0.113.13", "2001:db8:cb::13",  7),
    ("tn6-cb4",  "contabo", "chaos_contabo", "203.0.113.14", "2001:db8:cb::14", 10),
    ("tn6-cb5",  "contabo", "chaos_contabo", "203.0.113.15", "2001:db8:cb::15", 13),
    ("tn6-cb6",  "contabo", "chaos_contabo", "203.0.113.16", "2001:db8:cb::16", 16),
    ("tn6-cb7",  "contabo", "chaos_contabo", "203.0.113.17", "2001:db8:cb::17", 19),
    ("tn6-ovh2", "ovh",     "chaos_ovh",     "203.0.113.22", "2001:db8:ovh::22", 25),
    ("tn6-ovh3", "ovh",     "chaos_ovh",     "203.0.113.23", "2001:db8:ovh::23", 28),
    ("tn6-ovh4", "ovh",     "chaos_ovh",     "203.0.113.24", "2001:db8:ovh::24", 31),
    ("tn6-ovh5", "ovh",     "chaos_ovh",     "203.0.113.25", "2001:db8:ovh::25", 34),
]

TEMPLATE = """\
# host_vars/{host}.yml  — AUTO-GENERATED STUB
# Replace all REPLACE_ME and placeholder IPs (RFC 5737 / RFC 3849 ranges).
# See tn6-cb1.yml for the full annotated example.

provider: {provider}
chaos_group: {chaos_group}
host_label: {host}

host_ipv4: "{ipv4}"    # REPLACE_ME
host_ipv6: "{ipv6}"    # REPLACE_ME

pivx_instances:

  - name: {host}-v4-mn{mn_v4:02d}
    enabled: true
    slot: 0
    protocol_class: ipv4
    cohort: ipv4
    role: masternode
    bind_addr: "{{{{ host_ipv4 }}}}"
    external_ip: "{{{{ host_ipv4 }}}}"
    p2p_port: 51474
    rpc_port: 51478
    rpc_user: rpc_v4mn{mn_v4:02d}
    rpc_password: "{{{{ vault_pivx_rpc_password }}}}"
    datadir: "/var/lib/pivx/{host}-v4-mn{mn_v4:02d}"
    logdir: "/var/log/pivx/{host}-v4-mn{mn_v4:02d}"
    confdir: "/etc/pivx/{host}-v4-mn{mn_v4:02d}"
    bls_operator_key: "REPLACE_ME"
    extra_conf: []

  - name: {host}-v6-mn{mn_v6:02d}
    enabled: true
    slot: 1
    protocol_class: ipv6
    cohort: ipv6
    role: masternode
    bind_addr: "[{{{{ host_ipv6 }}}}]"
    external_ip: "{{{{ host_ipv6 }}}}"
    p2p_port: 51484
    rpc_port: 51488
    rpc_user: rpc_v6mn{mn_v6:02d}
    rpc_password: "{{{{ vault_pivx_rpc_password }}}}"
    datadir: "/var/lib/pivx/{host}-v6-mn{mn_v6:02d}"
    logdir: "/var/log/pivx/{host}-v6-mn{mn_v6:02d}"
    confdir: "/etc/pivx/{host}-v6-mn{mn_v6:02d}"
    bls_operator_key: "REPLACE_ME"
    extra_conf:
      - "ipv4=0"
      - "ipv6=1"

  - name: {host}-tor-mn{mn_tor:02d}
    enabled: true
    slot: 2
    protocol_class: tor
    cohort: tor
    role: masternode
    bind_addr: "127.0.0.1"
    external_ip: ""
    onion_service_dir: "/var/lib/tor/pivx_hs/{host}-tor-mn{mn_tor:02d}"
    p2p_port: 51494
    rpc_port: 51498
    rpc_user: rpc_tormn{mn_tor:02d}
    rpc_password: "{{{{ vault_pivx_rpc_password }}}}"
    datadir: "/var/lib/pivx/{host}-tor-mn{mn_tor:02d}"
    logdir: "/var/log/pivx/{host}-tor-mn{mn_tor:02d}"
    confdir: "/etc/pivx/{host}-tor-mn{mn_tor:02d}"
    bls_operator_key: "REPLACE_ME"
    extra_conf:
      - "onlynet=onion"
      - "proxy=127.0.0.1:9050"
      - "listen=1"
"""

def main():
    os.makedirs(BASE, exist_ok=True)
    for host, provider, chaos_group, ipv4, ipv6, mn_start in HOSTS:
        path = os.path.join(BASE, f"{host}.yml")
        if os.path.exists(path):
            print(f"SKIP  {path}  (exists)")
            continue
        content = TEMPLATE.format(
            host=host,
            provider=provider,
            chaos_group=chaos_group,
            ipv4=ipv4,
            ipv6=ipv6,
            mn_v4=mn_start,
            mn_v6=mn_start + 1,
            mn_tor=mn_start + 2,
        )
        with open(path, "w") as f:
            f.write(content)
        print(f"WROTE {path}")

if __name__ == "__main__":
    main()
