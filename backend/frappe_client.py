from __future__ import annotations

from functools import lru_cache

from frappeclient import FrappeClient

from .config import settings


class ErpCredentialsMissingError(RuntimeError):
	pass


@lru_cache(maxsize=1)
def get_frappe_client() -> FrappeClient:
	if not settings.ERP_API_KEY or not settings.ERP_API_SECRET:
		raise ErpCredentialsMissingError("Missing ERP_API_KEY/ERP_API_SECRET")

	return FrappeClient(settings.ERP_API_URL, settings.ERP_API_KEY, settings.ERP_API_SECRET)
