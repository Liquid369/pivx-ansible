# PIVX Testnet6 Ansible repo
#
# TESTNET LIFECYCLE (run in order):
#   1. make bootstrap              - OS prep (first-time only)
#   2. make deploy                 - Full initial deployment
#   3. make start-bootstrap-mining - Begin PoW mining to build chain height
#   4. make verify-readiness       - Poll fleet until height >= nFirstPoSBlock
#   5. make transition-to-pos      - Stop mining, set gen=0, restart
#   6. make enable-staking         - Verify staking wallets and unlock
#   7. make enable-masternodes     - Verify DMN status (register DMNs first!)
#   8. make upgrade-pivx PIVX_VERSION=6.0.0-test - Migrate to v6 feature binary
#   9. make chaos-inject-latency COHORT=tor DELAY=200ms  - Begin chaos testing
#
# REPEAT FROM GENESIS:
#   make wipe-chain-dry-run        - Preview what would be wiped
#   make wipe-chain                - Full chain wipe (keeps wallets by default)
#   Then restart from step 2.
#
# COMMON VARS:
#   LIMIT=tn6-cb1           limit to specific host(s)
#   COHORT=ipv4|ipv6|tor    for cohort-* and chaos-* targets
#   PROVIDER=contabo|ovh    for provider-* targets
#   DELAY=200ms             latency for chaos-inject-latency
#   JITTER=20ms             jitter for chaos-inject-latency
#   LOSS=5                  loss percent for chaos-inject-loss
#   PIVX_VERSION=x.y.z      for upgrade-pivx

INVENTORY      ?= ansible/inventories/testnet6
ANSIBLE_OPTS   ?=
LIMIT          ?=
COHORT         ?=
PROVIDER       ?=
DELAY          ?= 100ms
JITTER         ?= 10ms
LOSS           ?= 5
PIVX_VERSION   ?= latest
PYTHON         ?= $(shell test -x .venv/bin/python && echo .venv/bin/python || echo python3)
ANSIBLE_PLAYBOOK ?= $(shell test -x .venv/bin/ansible-playbook && echo .venv/bin/ansible-playbook || echo ansible-playbook)
ANSIBLE_LINT   ?= $(shell test -x .venv/bin/ansible-lint && echo .venv/bin/ansible-lint || echo ansible-lint)

# Limit flag: pass --limit only when LIMIT is set
ifdef LIMIT
  LIMIT_FLAG = --limit $(LIMIT)
else
  LIMIT_FLAG =
endif

PLAYBOOK = ANSIBLE_LOCAL_TEMP=.ansible/tmp $(ANSIBLE_PLAYBOOK) -i $(INVENTORY) $(ANSIBLE_OPTS) $(LIMIT_FLAG)

.PHONY: help \
        bootstrap deploy deploy-pivx deploy-monitoring deploy-tor \
        status check-inventory show-layout \
        start-bootstrap-mining stop-bootstrap-mining \
        verify-readiness transition-to-pos \
        enable-staking enable-masternodes \
        wipe-chain wipe-chain-dry-run \
        cohort-stop cohort-start cohort-restart \
        provider-stop provider-start \
        chaos-inject-latency chaos-inject-loss chaos-clear chaos-collect-debug \
        rolling-restart upgrade-pivx collect-debug collect-logs lint

help:
	@echo ""
	@echo "PIVX Testnet6 — Make Targets"
	@echo "============================================================"
	@echo ""
	@echo "TESTNET LIFECYCLE (run in order for a fresh chain):"
	@echo "  bootstrap              OS prep on all hosts (run once)"
	@echo "  deploy                 Full deployment: PIVX + monitoring + tor"
	@echo "  start-bootstrap-mining Begin PoW mining on bootstrap_miners group"
	@echo "  verify-readiness       Poll fleet: heights, peers, sync status"
	@echo "  transition-to-pos      Stop mining, set gen=0, restart (Phase 2→3)"
	@echo "  enable-staking         Verify staking status on staking nodes"
	@echo "  enable-masternodes     Verify DMN status on masternode nodes"
	@echo "  upgrade-pivx           Upgrade/migrate binary after MN/quorum baseline"
	@echo ""
	@echo "CHAIN WIPE / RESTART:"
	@echo "  wipe-chain-dry-run     Preview what wipe would do (no changes)"
	@echo "  wipe-chain             Full chain wipe, keeps wallets by default"
	@echo "                         Set KEEP_WALLET=false to also wipe wallets"
	@echo ""
	@echo "DEPLOYMENT:"
	@echo "  deploy-pivx            Deploy/reconfigure all PIVX instances"
	@echo "  deploy-monitoring      Deploy Prometheus/Grafana/Loki/Alertmanager"
	@echo "  deploy-tor             Deploy Tor hidden services"
	@echo ""
	@echo "INSPECTION:"
	@echo "  status                 Show fleet/instance status summary"
	@echo "  check-inventory        Validate inventory schema"
	@echo "  show-layout            Print host/instance layout"
	@echo "  collect-debug          Gather debug bundle from all hosts"
	@echo "  collect-logs           INSTANCE=<name> Shell log bundle for one instance"
	@echo ""
	@echo "COHORT OPS (COHORT=ipv4|ipv6|tor):"
	@echo "  cohort-stop            Stop all instances in protocol cohort"
	@echo "  cohort-start           Start all instances in protocol cohort"
	@echo "  cohort-restart         Restart all instances in protocol cohort"
	@echo ""
	@echo "PROVIDER OPS (PROVIDER=contabo|ovh):"
	@echo "  provider-stop          Stop all services on provider hosts"
	@echo "  provider-start         Start all services on provider hosts"
	@echo ""
	@echo "CHAOS / FAULT INJECTION:"
	@echo "  chaos-inject-latency COHORT=X [DELAY=100ms] [JITTER=10ms]  (host-level netem)"
	@echo "  chaos-inject-loss    COHORT=X [LOSS=5]                     (host-level netem)"
	@echo "  chaos-clear          COHORT=X   Remove all netem rules"
	@echo ""
	@echo "DAY-2 OPS:"
	@echo "  rolling-restart        Rolling restart of all masternode instances"
	@echo "  upgrade-pivx           Upgrade binary  PIVX_VERSION=x.y.z"
	@echo "  lint                   Run ansible-lint on all playbooks"
	@echo ""

# -----------------------------------------------------------------------------
# Environment setup
# -----------------------------------------------------------------------------
bootstrap:
	$(PLAYBOOK) ansible/playbooks/bootstrap.yml

# -----------------------------------------------------------------------------
# Full deploy
# -----------------------------------------------------------------------------
deploy:
	$(PLAYBOOK) ansible/playbooks/site.yml

deploy-pivx:
	$(PLAYBOOK) ansible/playbooks/deploy_pivx.yml

deploy-monitoring:
	$(PLAYBOOK) ansible/playbooks/deploy_monitoring.yml

deploy-tor:
	$(PLAYBOOK) ansible/playbooks/deploy_tor.yml

# -----------------------------------------------------------------------------
# Lifecycle — testnet phase transitions
# EDIT group_vars/all/main.yml:lifecycle_phase between runs as directed.
# -----------------------------------------------------------------------------

## Phase 2: bootstrap mining
start-bootstrap-mining:
	$(PLAYBOOK) ansible/playbooks/lifecycle/start_bootstrap_mining.yml

stop-bootstrap-mining:
	$(PLAYBOOK) ansible/playbooks/lifecycle/stop_bootstrap_mining.yml

## Readiness check (all phases)
verify-readiness:
	$(PLAYBOOK) ansible/playbooks/lifecycle/verify_phase_readiness.yml

## Phase 2 → 3
transition-to-pos:
	$(PLAYBOOK) ansible/playbooks/lifecycle/transition_to_pos.yml

## Phase 3: staking
enable-staking:
	$(PLAYBOOK) ansible/playbooks/lifecycle/enable_staking.yml

## Phase 4: masternodes / quorum
enable-masternodes:
	$(PLAYBOOK) ansible/playbooks/lifecycle/enable_masternodes.yml

## Chain wipe
wipe-chain-dry-run:
	$(PLAYBOOK) ansible/playbooks/lifecycle/wipe_chain.yml --check

wipe-chain:
	@echo "WARNING: This will wipe all chain data on ALL testnet hosts."
	@echo "Wallets are preserved by default (chain_wipe_keep_wallet=true)."
	@echo "Press Ctrl-C within 5s to abort..."
	@sleep 5
	$(PLAYBOOK) ansible/playbooks/lifecycle/wipe_chain.yml

# -----------------------------------------------------------------------------
# Status / inspection
# -----------------------------------------------------------------------------
status:
	$(PLAYBOOK) ansible/playbooks/ops/show_status.yml

check-inventory:
	$(PYTHON) scripts/validate_inventory.py $(INVENTORY)

show-layout:
	$(PYTHON) scripts/show_layout.py $(INVENTORY)

# -----------------------------------------------------------------------------
# Cohort operations
# -----------------------------------------------------------------------------
cohort-stop:
	@test -n "$(COHORT)" || (echo "ERROR: Set COHORT=ipv4|ipv6|tor"; exit 1)
	$(PLAYBOOK) ansible/playbooks/chaos/stop_cohort.yml -e "target_cohort=$(COHORT)"

cohort-start:
	@test -n "$(COHORT)" || (echo "ERROR: Set COHORT=ipv4|ipv6|tor"; exit 1)
	$(PLAYBOOK) ansible/playbooks/chaos/start_cohort.yml -e "target_cohort=$(COHORT)"

cohort-restart:
	@test -n "$(COHORT)" || (echo "ERROR: Set COHORT=ipv4|ipv6|tor"; exit 1)
	$(PLAYBOOK) ansible/playbooks/chaos/restart_cohort.yml -e "target_cohort=$(COHORT)"

# -----------------------------------------------------------------------------
# Provider operations
# -----------------------------------------------------------------------------
provider-stop:
	@test -n "$(PROVIDER)" || (echo "ERROR: Set PROVIDER=contabo|ovh"; exit 1)
	$(PLAYBOOK) ansible/playbooks/chaos/stop_provider.yml -e "target_provider=$(PROVIDER)"

provider-start:
	@test -n "$(PROVIDER)" || (echo "ERROR: Set PROVIDER=contabo|ovh"; exit 1)
	$(PLAYBOOK) ansible/playbooks/chaos/start_provider.yml -e "target_provider=$(PROVIDER)"

# -----------------------------------------------------------------------------
# Chaos / fault injection
# -----------------------------------------------------------------------------
chaos-inject-latency:
	@test -n "$(COHORT)" || (echo "ERROR: Set COHORT=ipv4|ipv6|tor"; exit 1)
	$(PLAYBOOK) ansible/playbooks/chaos/inject_latency.yml \
	  -e "target_cohort=$(COHORT)" \
	  -e "netem_latency=$(DELAY)" \
	  -e "netem_jitter=$(JITTER)"

chaos-inject-loss:
	@test -n "$(COHORT)" || (echo "ERROR: Set COHORT=ipv4|ipv6|tor"; exit 1)
	$(PLAYBOOK) ansible/playbooks/chaos/inject_loss.yml \
	  -e "target_cohort=$(COHORT)" \
	  -e "netem_loss_percent=$(LOSS)%"

chaos-clear:
	@test -n "$(COHORT)" || (echo "ERROR: Set COHORT=ipv4|ipv6|tor"; exit 1)
	$(PLAYBOOK) ansible/playbooks/chaos/clear_netem.yml \
	  -e "target_cohort=$(COHORT)"

collect-debug:
	$(PLAYBOOK) ansible/playbooks/chaos/collect_debug.yml

## collect-logs INSTANCE=<name> [FLAGS=--quorum]   - shell-based single-instance log bundle
collect-logs:
	@test -n "$(INSTANCE)" || (echo "ERROR: Set INSTANCE=<instance-name>  e.g. make collect-logs INSTANCE=tn6-cb1-tor-mn05"; exit 1)
	scripts/collect_logs.sh $(INSTANCE) $(FLAGS)

# Keep old alias for back-compat
chaos-collect-debug: collect-debug

# -----------------------------------------------------------------------------
# Day-2 ops
# -----------------------------------------------------------------------------
rolling-restart:
	$(PLAYBOOK) ansible/playbooks/chaos/rolling_restart.yml

upgrade-pivx:
	$(PLAYBOOK) ansible/playbooks/upgrade_pivx.yml \
	  -e "pivx_version=$(PIVX_VERSION)"

# -----------------------------------------------------------------------------
# Quality
# -----------------------------------------------------------------------------
lint:
	XDG_CACHE_HOME=.cache ANSIBLE_LOCAL_TEMP=.ansible/tmp $(ANSIBLE_LINT) ansible/playbooks/site.yml
