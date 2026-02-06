#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"

DEFAULT_PRE_COMMIT_HOME="${XDG_CACHE_HOME:-$HOME/.cache}/pre-commit"
CANDIDATE_PRE_COMMIT_HOME="${PRE_COMMIT_HOME:-$DEFAULT_PRE_COMMIT_HOME}"

is_writable_dir() {
	local dir="$1"
	mkdir -p "$dir" 2>/dev/null || return 1

	# `mkdir -p` succeeds even if the dir exists but is not writable under sandboxed environments.
	# Probe actual writability.
	local probe
	probe="$(mktemp "$dir/.writetest.XXXXXXXX" 2>/dev/null)" || return 1
	rm -f "$probe" 2>/dev/null || true
	return 0
}

if ! is_writable_dir "$CANDIDATE_PRE_COMMIT_HOME"; then
	CANDIDATE_PRE_COMMIT_HOME="$ROOT/.cache/pre-commit"
	mkdir -p "$CANDIDATE_PRE_COMMIT_HOME"
fi

export PRE_COMMIT_HOME="$CANDIDATE_PRE_COMMIT_HOME"

pre-commit run --all-files "$@"
