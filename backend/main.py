from __future__ import annotations

"""Compatibility wrapper for the FastAPI backend.

Canonical implementation lives under `ferum_custom.integrations.fastapi_backend`.
Keep historical entrypoints like `uvicorn backend.main:app` working.
"""

from ferum_custom.integrations.fastapi_backend.main import app
