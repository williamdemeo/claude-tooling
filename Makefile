# Makefile — claude-tooling: William's versioned Claude Code configuration.
# All targets log verbosely in real time (green ✓ / red ✗ per item).
# The *.sh entry points are shims into scripts/ct.py (python >= 3.11, stdlib).
SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

# Pass-through knobs:  make install PROJECT=fls DRY_RUN=1 FORCE=1
PROJECT ?=
DRY_RUN ?=
FORCE   ?=

.PHONY: help install check lint test probe list verify-discovery stale-worktrees

help: ## show available targets
	@awk -F':.*## ' '/^[a-z-]+:.*## /{printf "  make %-18s %s\n", $$1, $$2}' Makefile
	@echo '  variables: PROJECT=<name|global>  DRY_RUN=1  FORCE=1'

install: ## symlink config into place from this repo (idempotent, backups under --force)
	./install.sh $(if $(DRY_RUN),--dry-run) $(if $(FORCE),--force) $(PROJECT)

check: ## static verification — manifest, lint, link state; zero tokens
	scripts/check.sh $(PROJECT)

lint: ## repo hygiene only — skills, markers, secret shapes; zero tokens
	python3 scripts/ct.py lint

test: ## unit tests for scripts/ct.py (tmp fixtures only; never touches live config)
	python3 -m unittest discover -s scripts -q

probe: ## LIVE verification matrix — spawns real claude -p sessions (costs tokens)
	scripts/probe.sh $(PROJECT)

list: ## inventory of managed CLAUDE.md files and skills by tier
	scripts/list.sh

stale-worktrees: ## scan for merged/stale worktrees; prints removals (REMOVE=1 executes them)
	scripts/stale-worktrees.sh $(if $(REMOVE),--remove) $(PROJECT)

verify-discovery: ## re-verify the discovery rules with throwaway fixtures (costs tokens)
	scripts/verify-discovery.sh
