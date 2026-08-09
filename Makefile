# Makefile — claude-tooling: William's versioned Claude Code configuration.
# All targets log verbosely in real time (green ✓ / red ✗ per item).
SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

# Pass-through knobs:  make install PROJECT=fls DRY_RUN=1 FORCE=1
PROJECT ?=
DRY_RUN ?=
FORCE   ?=

.PHONY: help install check probe list verify-discovery

help: ## show available targets
	@awk -F':.*## ' '/^[a-z-]+:.*## /{printf "  make %-18s %s\n", $$1, $$2}' Makefile
	@echo '  variables: PROJECT=<name|global>  DRY_RUN=1  FORCE=1'

install: ## symlink config into place from this repo (idempotent, backups under --force)
	./install.sh $(if $(DRY_RUN),--dry-run) $(if $(FORCE),--force) $(PROJECT)

check: ## static verification — manifest, lint, link state; zero tokens
	scripts/check.sh $(PROJECT)

probe: ## LIVE verification matrix — spawns real claude -p sessions (costs tokens)
	scripts/probe.sh $(PROJECT)

list: ## inventory of managed CLAUDE.md files and skills by tier
	scripts/list.sh

verify-discovery: ## re-verify the discovery rules with throwaway fixtures (costs tokens)
	scripts/verify-discovery.sh
