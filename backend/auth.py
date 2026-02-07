from __future__ import annotations

"""Compatibility wrapper for auth helpers."""

from ferum_custom.integrations.fastapi_backend.auth import (
	create_access_token,
	get_current_user,
	has_role,
	verify_token,
)
