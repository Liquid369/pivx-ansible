#!/usr/bin/env python3
"""
validate_inventory.py — Validate Testnet6 Ansible inventory sanity.

Usage:
    python3 scripts/validate_inventory.py ansible/inventories/testnet6

Checks:
  - All instance names are globally unique
  - No port conflicts within a host
  - Required fields present for each instance
  - bls_operator_key is not REPLACE_ME if role==masternode and enabled==True
  - host_ipv6 set when any instance has protocol_class==ipv6
  - onion_service_dir set when protocol_class==tor
"""

import sys
import os
import yaml
from pathlib import Path
from collections import defaultdict

REQUIRED_INSTANCE_FIELDS = [
    "name", "enabled", "slot", "protocol_class", "cohort",
    "role", "bind_addr", "p2p_port", "rpc_port",
    "rpc_user", "rpc_password", "datadir", "logdir", "confdir",
]

ERRORS = []
WARNINGS = []


def err(msg: str):
    ERRORS.append(f"  ERROR: {msg}")


def warn(msg: str):
    WARNINGS.append(f"  WARN:  {msg}")


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_host_vars(inv_dir: Path) -> dict[str, dict]:
    hv_dir = inv_dir / "host_vars"
    host_vars = {}
    if not hv_dir.exists():
        return host_vars
    for f in sorted(hv_dir.glob("*.yml")):
        hostname = f.stem
        try:
            host_vars[hostname] = load_yaml(f)
        except Exception as e:
            err(f"Failed to parse {f}: {e}")
    return host_vars


def validate_instances(all_host_vars: dict[str, dict]):
    seen_names: set[str] = set()
    seen_ports: dict[str, set[tuple]] = defaultdict(set)  # host -> {(port,proto)}

    for hostname, hvars in all_host_vars.items():
        instances = hvars.get("pivx_instances", [])
        if not instances:
            # Hosts without instances (monitoring-only) are OK
            continue

        for inst in instances:
            name = inst.get("name", "UNNAMED")
            enabled = inst.get("enabled", True)

            # Uniqueness
            if name in seen_names:
                err(f"Duplicate instance name '{name}' found on host {hostname}")
            seen_names.add(name)

            # Required fields
            for field in REQUIRED_INSTANCE_FIELDS:
                if field not in inst:
                    err(f"{hostname}/{name}: missing required field '{field}'")

            # Port conflicts within host
            p2p = inst.get("p2p_port")
            rpc = inst.get("rpc_port")
            if p2p:
                key = (p2p, "tcp")
                if key in seen_ports[hostname]:
                    err(f"{hostname}/{name}: p2p_port {p2p} conflicts with another instance on this host")
                seen_ports[hostname].add(key)
            if rpc:
                key = (rpc, "tcp")
                if key in seen_ports[hostname]:
                    err(f"{hostname}/{name}: rpc_port {rpc} conflicts with another instance on this host")
                seen_ports[hostname].add(key)

            # BLS key placeholder check
            role = inst.get("role", "")
            bls = inst.get("bls_operator_key", "")
            if role == "masternode" and enabled and bls in ("REPLACE_ME", "", None):
                warn(f"{hostname}/{name}: bls_operator_key is unset/placeholder (must be filled before deploy)")

            # IPv6 requires host_ipv6
            proto = inst.get("protocol_class", "")
            if proto == "ipv6" and not hvars.get("host_ipv6"):
                err(f"{hostname}/{name}: protocol_class=ipv6 but host_ipv6 not set in host_vars")

            # Tor requires onion_service_dir
            if proto == "tor" and not inst.get("onion_service_dir"):
                err(f"{hostname}/{name}: protocol_class=tor but onion_service_dir not set")

            # Validate cohort matches protocol_class
            cohort = inst.get("cohort", "")
            if cohort and cohort != proto:
                warn(f"{hostname}/{name}: cohort='{cohort}' does not match protocol_class='{proto}'")


def validate_placeholder_ips(all_host_vars: dict[str, dict]):
    placeholder_ranges = ["203.0.113.", "2001:db8:"]
    for hostname, hvars in all_host_vars.items():
        for field in ["host_ipv4", "host_ipv6"]:
            val = hvars.get(field, "")
            if val and any(val.startswith(p) for p in placeholder_ranges):
                warn(f"{hostname}: {field}='{val}' looks like a placeholder — replace with real IP")


def main():
    if len(sys.argv) < 2:
        print("Usage: validate_inventory.py <inventory_dir>")
        sys.exit(1)

    inv_dir = Path(sys.argv[1])
    if not inv_dir.exists():
        print(f"Inventory directory not found: {inv_dir}")
        sys.exit(1)

    print(f"\nValidating inventory: {inv_dir}\n")

    all_host_vars = load_host_vars(inv_dir)
    print(f"Loaded host_vars for {len(all_host_vars)} hosts: {sorted(all_host_vars.keys())}\n")

    validate_instances(all_host_vars)
    validate_placeholder_ips(all_host_vars)

    if WARNINGS:
        print("Warnings:")
        for w in WARNINGS:
            print(w)
        print()

    if ERRORS:
        print("Errors:")
        for e in ERRORS:
            print(e)
        print(f"\n{len(ERRORS)} error(s) found. Fix before deploying.")
        sys.exit(1)
    else:
        print(f"All checks passed. {len(WARNINGS)} warning(s).")
        sys.exit(0)


if __name__ == "__main__":
    main()
