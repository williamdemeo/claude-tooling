#!/usr/bin/env sh
# Shim: the implementation is scripts/ct.py (python >= 3.11, stdlib only).
exec python3 "$(dirname "$0")/ct.py" list "$@"
