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

pre-commit install
pre-commit install --hook-type pre-push

patch_hook() {
	local hook_name="$1"
	local hook_path="$ROOT/.git/hooks/$hook_name"

	[ -f "$hook_path" ] || return 0

	# Idempotent: skip if already patched
	if grep -q "PRE_COMMIT_HOME=.*\\.cache/pre-commit" "$hook_path" 2>/dev/null; then
		return 0
	fi

	# Insert right after the shebang to ensure it's applied for hook execution.
	local tmp
	tmp="$(mktemp)"
	{
		IFS= read -r first_line || true
		printf '%s\n' "$first_line"
		printf '%s\n' 'PRE_COMMIT_HOME="$(git rev-parse --show-toplevel)/.cache/pre-commit"'
		printf '%s\n' 'export PRE_COMMIT_HOME'
		printf '%s\n' 'mkdir -p "$PRE_COMMIT_HOME" >/dev/null 2>&1 || true'
		cat
	} <"$hook_path" >"$tmp"
	mv "$tmp" "$hook_path"
	chmod +x "$hook_path" 2>/dev/null || true
}

patch_hook pre-commit
patch_hook pre-push

echo "Installed git hooks: pre-commit + pre-push"
echo "PRE_COMMIT_HOME=$PRE_COMMIT_HOME"
