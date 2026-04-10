#!/usr/bin/env bash
# scripts/collect_logs.sh
#
# Collect recent journal logs and chain state for one or more PIVX instances.
# Outputs are saved to debug-bundles/<instance>-<timestamp>/ on this machine.
#
# Usage:
#   ./scripts/collect_logs.sh <instance-name>
#   ./scripts/collect_logs.sh <instance-name> --quorum
#   ./scripts/collect_logs.sh <instance-name> --lines 1000
#   ./scripts/collect_logs.sh tn6-cb1-tor-mn03
#   ./scripts/collect_logs.sh tn6-cb1-tor-mn03 --quorum --lines 500
#
# Requires:
#   - SSH access to the host via the ansible_host in host_vars
#   - ansible-inventory available in PATH
#   - jq for pretty-printing JSON output

set -euo pipefail

INVENTORY="ansible/inventories/testnet6"
LINES=500
QUORUM=false
INSTANCE=""

# ── Parse arguments ──────────────────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --quorum)   QUORUM=true ;;
    --lines=*)  LINES="${arg#*=}" ;;
    --lines)    shift; LINES="${1:-500}" ;;
    -*)         echo "Unknown option: $arg"; exit 1 ;;
    *)          INSTANCE="$arg" ;;
  esac
done

if [[ -z "$INSTANCE" ]]; then
  echo "Usage: $0 <instance-name> [--quorum] [--lines N]"
  echo ""
  echo "Examples:"
  echo "  $0 tn6-cb1-tor-mn03"
  echo "  $0 tn6-seed01 --quorum --lines 1000"
  exit 1
fi

# ── Find the host that owns this instance ────────────────────────────────────
echo "Looking up host for instance: ${INSTANCE}"

# Query ansible-inventory to find which host has this instance in pivx_instances
HOST=$(ansible-inventory -i "$INVENTORY" --list 2>/dev/null \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
instance_name = '${INSTANCE}'
for host, hvars in data.get('_meta', {}).get('hostvars', {}).items():
    for inst in hvars.get('pivx_instances', []):
        if inst.get('name') == instance_name:
            print(host)
            sys.exit(0)
print('')
" 2>/dev/null || true)

if [[ -z "$HOST" ]]; then
  echo "ERROR: Could not find instance '${INSTANCE}' in inventory."
  echo "Run 'python3 scripts/validate_inventory.py' for a full instance list."
  exit 1
fi

echo "Found instance '${INSTANCE}' on host: ${HOST}"

# ── Get the host's SSH address ───────────────────────────────────────────────
HOST_IP=$(ansible-inventory -i "$INVENTORY" --host "$HOST" 2>/dev/null \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('ansible_host', ''))" \
  || true)

if [[ -z "$HOST_IP" ]]; then
  echo "ERROR: Could not find ansible_host for ${HOST}"
  exit 1
fi

SSH_USER=$(ansible-inventory -i "$INVENTORY" --host "$HOST" 2>/dev/null \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('ansible_user', 'root'))" \
  || echo "root")

echo "SSH target: ${SSH_USER}@${HOST_IP}"

# ── Create output directory ───────────────────────────────────────────────────
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BUNDLE_DIR="debug-bundles/${INSTANCE}-${TIMESTAMP}"
mkdir -p "$BUNDLE_DIR"
echo "Output directory: ${BUNDLE_DIR}/"

# ── Collect via SSH ───────────────────────────────────────────────────────────
CONF_DIR="/etc/pivx/${INSTANCE}"
DATA_DIR="/var/lib/pivx/${INSTANCE}"
PIVX_CLI="/opt/pivx/current/bin/pivx-cli"
CLI="$PIVX_CLI -conf=${CONF_DIR}/pivx.conf -datadir=${DATA_DIR}"

ssh_run() {
  ssh -o ConnectTimeout=10 -o BatchMode=yes "${SSH_USER}@${HOST_IP}" "$@" 2>&1 || true
}

echo ""
echo "Collecting data from ${HOST_IP}..."

# Service status
echo "[1/7] systemctl status..."
ssh_run "systemctl status pivxd@${INSTANCE} --no-pager" > "${BUNDLE_DIR}/service_status.txt"

# Journal logs
echo "[2/7] journal logs (last ${LINES} lines)..."
ssh_run "journalctl -u pivxd@${INSTANCE} -n ${LINES} --no-pager" > "${BUNDLE_DIR}/journal.txt"

# getblockchaininfo
echo "[3/7] getblockchaininfo..."
ssh_run "${CLI} getblockchaininfo 2>&1" > "${BUNDLE_DIR}/blockchaininfo.json"

# getpeerinfo
echo "[4/7] getpeerinfo..."
ssh_run "${CLI} getpeerinfo 2>&1" > "${BUNDLE_DIR}/peerinfo.json"

# getconnectioncount
echo "[5/7] getconnectioncount..."
ssh_run "${CLI} getconnectioncount 2>&1" > "${BUNDLE_DIR}/peercount.txt"

# Network state
echo "[6/7] network state..."
ssh_run "ss -tlnp 2>/dev/null; echo '---'; ip route show 2>/dev/null" > "${BUNDLE_DIR}/network.txt"

# Config file (redacted)
echo "[7/7] pivx.conf (redacted)..."
ssh_run "cat ${CONF_DIR}/pivx.conf 2>/dev/null | sed 's/rpcpassword=.*/rpcpassword=REDACTED/'" \
  > "${BUNDLE_DIR}/pivx.conf.txt"

# Quorum data (if requested)
if [[ "$QUORUM" == "true" ]]; then
  echo "[+] quorum data..."
  ssh_run "${CLI} masternode status 2>&1" > "${BUNDLE_DIR}/masternode_status.json"
  ssh_run "${CLI} quorum list 2>&1" > "${BUNDLE_DIR}/quorum_list.json"
  ssh_run "${CLI} quorum dkgstatus 2>&1" > "${BUNDLE_DIR}/dkg_status.json"
fi

# Chaos log if present
ssh_run "tail -100 /var/log/pivx/chaos.log 2>/dev/null || echo 'no chaos.log'" \
  > "${BUNDLE_DIR}/chaos_log.txt"

echo ""
echo "Done. Bundle saved to: ${BUNDLE_DIR}/"
echo ""
echo "Files collected:"
ls -lh "${BUNDLE_DIR}/"
echo ""
echo "Quick triage:"
echo "  Block height : $(grep -o '"blocks":[0-9]*' "${BUNDLE_DIR}/blockchaininfo.json" | head -1 || echo 'N/A')"
echo "  Peer count   : $(cat "${BUNDLE_DIR}/peercount.txt" 2>/dev/null | head -1 || echo 'N/A')"
echo "  Service state: $(grep -o 'Active:.*' "${BUNDLE_DIR}/service_status.txt" | head -1 || echo 'N/A')"

if grep -q "ERROR\|WARN" "${BUNDLE_DIR}/journal.txt" 2>/dev/null; then
  echo ""
  echo "Recent ERROR/WARN lines:"
  grep -E "ERROR|WARN" "${BUNDLE_DIR}/journal.txt" | tail -10
fi
