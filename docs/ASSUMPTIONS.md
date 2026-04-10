# Engineering Assumptions

This document records explicit assumptions made during the design and build of
this repository. Review these before first deployment and update as decisions
are confirmed or changed.

---

## OS and Platform

| Assumption | Rationale | Risk |
|------------|-----------|------|
| Ubuntu 22.04 LTS on all nodes | LTS = long-term apt packages, well-tested with PIVX deps | If a host runs a different OS, bootstrap.yml will fail the version assertion. Override or extend roles. |
| x86_64 architecture on all hosts | PIVX release binaries ship as `linux-amd64` | ARM hosts require a custom build or separate download URL. |
| Contabo and OVH support dual-stack (IPv4+IPv6) | Required for IPv6 instances | Confirm with provider before deploy. Some OVH plans require IPv6 to be manually enabled. |

---

## PIVX Software

| Assumption | Rationale | Risk |
|------------|-----------|------|
| PIVX v6.0 / testnet6 binary is published on GitHub Releases | Standard PIVX release channel | If the binary is a pre-release or private build, update `pivx_archive_url` and `pivx_checksum` manually. |
| testnet6 uses standard PIVX testnet P2P port 51474 | Default testnet port | If testnet6 uses a custom port, update `pivx_p2p_port_base` in group_vars. |
| `masternodeblsprivkey=` is the correct config key for DMN operator key | Current PIVX masternode config | Confirm against PIVX v6.0 documentation. Field name may differ if the config format changed. |
| `debug=llmq` and `debug=masternode` log categories exist | Used in PIVX 5.x+ | Confirm these debug categories are still valid in v6.0. |

---

## DMN Registration

| Assumption | Rationale | Risk |
|------------|-----------|------|
| Collateral is 10,000 PIVX per masternode instance | Standard PIVX MN collateral | Confirm. Testnet may use a different collateral amount to reduce cost. |
| DMN registration is done externally with a PIVX wallet | This is the standard process | If PIVX v6.0 changes the registration flow significantly, update DEPLOYMENT_PLAN.md. |
| Onion addresses for Tor masternodes are stable once created | Tor v3 HS keys persist in `onion_service_dir` | Keys are in `/var/lib/tor/pivx_hs/<instance>/private_key`. Back these up if HS identity needs to persist. |

---

## Ansible and Tooling

| Assumption | Rationale | Risk |
|------------|-----------|------|
| Ansible 2.14+ on the control machine | Uses `ansible.builtin.*` FQCN style | Older Ansible may not support all task options. |
| `community.general` and `ansible.posix` collections are installed | Required for ufw, sysctl, archive tasks | Run `ansible-galaxy collection install community.general ansible.posix` before first use. |
| Python 3.9+ on control machine | Required for scripts/ | Scripts use f-strings and walrus operators. |

---

## Observability

| Assumption | Rationale | Risk |
|------------|-----------|------|
| No PIVX-specific Prometheus exporter exists yet | Not found in PIVX ecosystem | Prometheus alerts marked `PLACEHOLDER` require a PIVX exporter or script-based scraper. **High priority item.** |
| Vector 0.37+ provides a working journald source | Tested in Vector docs | Vector journald on Ubuntu 22.04 requires `systemd-journal-gateway` or direct privileged access. Confirm vector group membership includes `systemd-journal`. |
| Loki can handle 15-host × 3-instance label cardinality | 45 unique `instance` values | This is well within Loki's default cardinality limits. |

---

## Network

| Assumption | Rationale | Risk |
|------------|-----------|------|
| IPv6 is available and configured (not just assigned) | IPv6 masternodes require routable IPv6 | Some VPS providers assign IPv6 but require manual interface config. Verify with `ip -6 addr show` after bootstrap. |
| Tor v3 hidden services are reachable from other nodes | Standard Tor network | If testnet6 nodes block Tor exit traffic, Tor cohort connectivity may fail silently. |
| Port 51474 is not blocked at the provider firewall level | Common P2P port | Some Contabo/OVH plans block non-standard ports. Verify initial firewall policy. |

---

## Security

| Assumption | Rationale | Risk |
|------------|-----------|------|
| `vault_pass.txt` is on the control machine and not committed | `.gitignore`'d | If vault_pass.txt is lost, vault.yml must be decrypted and re-encrypted with a new password. |
| deploy user has NOPASSWD sudo | Required for Ansible privilege escalation | If sudo requires a password, add `--ask-become-pass` to Ansible commands or configure NOPASSWD explicitly. |

---

## Outstanding Decisions (Human Input Required)

1. **Real IP addresses**: Replace all RFC 5737 / RFC 3849 placeholder IPs.
2. **PIVX version and checksum**: Confirm release tag and SHA256 before deploy.
3. **DMN collateral amount**: 10,000 PIVX assumed — verify for testnet6.
4. **IPv6 interface config on providers**: Confirm dual-stack is routable before deploying IPv6 instances.
5. **PIVX Prometheus exporter**: Build or find one to enable instance-level alerting.
6. **Quorum size parameters**: The "how many masternodes does quorum require?" threshold is not hardcoded here — it comes from the PIVX chain params. Document the actual expected thresholds when known.
7. **Alertmanager Slack workspace**: Populate `vault_alertmanager_slack_webhook` with a real webhook.
8. **Backup strategy**: No backup of masternodes datadirs or Tor HS keys is implemented. Decide on backup policy.
9. **Access control to monitoring**: Grafana and Prometheus are currently firewalled to localhost only. Decide who needs access and open accordingly.
