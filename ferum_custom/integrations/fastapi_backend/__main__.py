from __future__ import annotations

"""Module entrypoint for the FastAPI backend (no server runner).

This package provides the FastAPI `app` and routers. Running the service is typically done via:

`uvicorn backend.main:app` (compat path) or `uvicorn ferum_custom.integrations.fastapi_backend.main:app`.
"""

from .main import app
