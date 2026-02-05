#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
export PRE_COMMIT_HOME="${PRE_COMMIT_HOME:-$ROOT/.cache/pre-commit}"

mkdir -p "$PRE_COMMIT_HOME"

pre-commit install
pre-commit install --hook-type pre-push

echo "Installed git hooks: pre-commit + pre-push"
echo "PRE_COMMIT_HOME=$PRE_COMMIT_HOME"
