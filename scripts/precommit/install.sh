#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"

DEFAULT_PRE_COMMIT_HOME="${XDG_CACHE_HOME:-$HOME/.cache}/pre-commit"
CANDIDATE_PRE_COMMIT_HOME="${PRE_COMMIT_HOME:-$DEFAULT_PRE_COMMIT_HOME}"

if ! mkdir -p "$CANDIDATE_PRE_COMMIT_HOME" 2>/dev/null; then
	CANDIDATE_PRE_COMMIT_HOME="$ROOT/.cache/pre-commit"
	mkdir -p "$CANDIDATE_PRE_COMMIT_HOME"
fi

export PRE_COMMIT_HOME="$CANDIDATE_PRE_COMMIT_HOME"

pre-commit install
pre-commit install --hook-type pre-push

echo "Installed git hooks: pre-commit + pre-push"
echo "PRE_COMMIT_HOME=$PRE_COMMIT_HOME"
