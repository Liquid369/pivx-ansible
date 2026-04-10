#!/usr/bin/env python3
"""
show_layout.py — Print a human-readable summary of the host/instance layout.

Usage:
    python3 scripts/show_layout.py ansible/inventories/testnet6

Output:
    Table of hosts x instances with protocol, role, cohort, ports.
    Summary totals per cohort and provider.
"""

import sys
import yaml
from pathlib import Path
from collections import defaultdict


def load_host_vars(inv_dir: Path) -> dict[str, dict]:
    hv_dir = inv_dir / "host_vars"
    host_vars = {}
    if hv_dir.exists():
        for f in sorted(hv_dir.glob("*.yml")):
            with open(f) as fh:
                host_vars[f.stem] = yaml.safe_load(fh) or {}
    return host_vars


def main():
    if len(sys.argv) < 2:
        print("Usage: show_layout.py <inventory_dir>")
        sys.exit(1)

    inv_dir = Path(sys.argv[1])
    all_host_vars = load_host_vars(inv_dir)

    total_instances = 0
    cohort_counts: dict[str, int] = defaultdict(int)
    provider_counts: dict[str, int] = defaultdict(int)
    role_counts: dict[str, int] = defaultdict(int)

    print("\n" + "=" * 90)
    print(f"{'HOST':<14} {'PROVIDER':<10} {'INSTANCE':<26} {'PROTO':<6} {'ROLE':<12} {'P2P':<7} {'RPC'}")
    print("=" * 90)

    for hostname in sorted(all_host_vars.keys()):
        hvars = all_host_vars[hostname]
        provider = hvars.get("provider", "?")
        instances = hvars.get("pivx_instances", [])

        if not instances:
            print(f"{hostname:<14} {provider:<10} {'(no instances)'}")
            continue

        for i, inst in enumerate(instances):
            name = inst.get("name", "?")
            proto = inst.get("protocol_class", "?")
            role = inst.get("role", "?")
            p2p = inst.get("p2p_port", "?")
            rpc = inst.get("rpc_port", "?")
            enabled = inst.get("enabled", True)
            status = "" if enabled else " [disabled]"

            host_col = hostname if i == 0 else ""
            prov_col = provider if i == 0 else ""
            print(f"{host_col:<14} {prov_col:<10} {name:<26} {proto:<6} {role:<12} {str(p2p):<7} {rpc}{status}")

            if enabled:
                total_instances += 1
                cohort_counts[inst.get("cohort", "?")] += 1
                provider_counts[provider] += 1
                role_counts[role] += 1

        print("-" * 90)

    print()
    print(f"Total enabled instances : {total_instances}")
    print()
    print("By cohort:")
    for cohort, count in sorted(cohort_counts.items()):
        print(f"  {cohort:<10} {count}")
    print()
    print("By provider:")
    for prov, count in sorted(provider_counts.items()):
        print(f"  {prov:<10} {count}")
    print()
    print("By role:")
    for role, count in sorted(role_counts.items()):
        print(f"  {role:<14} {count}")
    print()


if __name__ == "__main__":
    main()
