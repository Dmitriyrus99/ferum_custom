#!/usr/bin/env bash
set -euo pipefail

# Some restricted sandboxes forbid creating sockets, which makes FastAPI's TestClient hang.
# In that case we skip backend unit tests locally and rely on CI.
if ! python - <<'PY'
import socket
import sys

try:
	s = socket.socket()
	s.close()
except PermissionError:
	sys.exit(1)
PY
then
	echo "SKIP: sockets are not permitted; skipping backend pytest." >&2
	exit 0
fi

python -m pytest backend/tests
