from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import requests

from ferum_custom.config.types import clean_str, is_truthy, parse_int


class VaultError(RuntimeError):
	pass


VaultAuthMethod = Literal["token", "approle", "missing"]


@dataclass(frozen=True)
class VaultConfig:
	addr: str
	mount: str
	path: str
	auth: VaultAuthMethod

	# Auth
	token: str | None = None
	role_id: str | None = None
	secret_id: str | None = None

	# TLS / HTTP
	namespace: str | None = None
	verify: bool | str = True
	cert: str | tuple[str, str] | None = None
	timeout_seconds: int = 20

	# Caching
	cache_ttl_seconds: int = 60


def _vault_verify_param(get: Any) -> bool | str:
	if is_truthy(get("VAULT_SKIP_VERIFY") or get("FERUM_VAULT_SKIP_VERIFY")):
		return False
	ca = get("VAULT_CACERT") or get("FERUM_VAULT_CACERT") or get("VAULT_CA_CERT")
	return str(ca).strip() if ca else True


def _vault_client_cert(get: Any) -> str | tuple[str, str] | None:
	cert = clean_str(get("VAULT_CLIENT_CERT") or get("FERUM_VAULT_CLIENT_CERT"))
	key = clean_str(get("VAULT_CLIENT_KEY") or get("FERUM_VAULT_CLIENT_KEY"))
	if cert and key:
		return cert, key
	if cert:
		return cert
	return None


def _vault_headers(*, token: str | None, namespace: str | None) -> dict[str, str]:
	headers: dict[str, str] = {}
	if namespace:
		headers["X-Vault-Namespace"] = namespace
	if token:
		headers["X-Vault-Token"] = token
	return headers


def _read_secret_file(raw: Any) -> str | None:
	path = clean_str(raw)
	if not path:
		return None
	try:
		return clean_str(Path(path).read_text(encoding="utf-8", errors="ignore"))
	except Exception:
		return None


def vault_config_from_getter(get: Any) -> VaultConfig | None:
	"""Build Vault config from a getter (env/frappe.conf/etc).

	The getter must behave like `dict.get`: `get(key) -> Any`.
	"""
	addr = clean_str(get("VAULT_ADDR") or get("FERUM_VAULT_ADDR"))
	path = clean_str(get("VAULT_PATH") or get("FERUM_VAULT_PATH"))
	if not addr or not path:
		return None

	mount = clean_str(get("VAULT_MOUNT") or get("FERUM_VAULT_MOUNT")) or "secret"

	token = clean_str(get("VAULT_TOKEN") or get("FERUM_VAULT_TOKEN"))
	if not token:
		token = _read_secret_file(get("VAULT_TOKEN_FILE") or get("FERUM_VAULT_TOKEN_FILE"))
	role_id = clean_str(get("VAULT_ROLE_ID") or get("FERUM_VAULT_ROLE_ID"))
	if not role_id:
		role_id = _read_secret_file(get("VAULT_ROLE_ID_FILE") or get("FERUM_VAULT_ROLE_ID_FILE"))
	secret_id = clean_str(get("VAULT_SECRET_ID") or get("FERUM_VAULT_SECRET_ID"))
	if not secret_id:
		secret_id = _read_secret_file(
			get("VAULT_SECRET_ID_FILE")
			or get("FERUM_VAULT_SECRET_ID_FILE")
			or get("VAULT_APPROLE_SECRET_ID_FILE")
			or get("FERUM_VAULT_APPROLE_SECRET_ID_FILE")
		)

	auth: VaultAuthMethod = "missing"
	if token:
		auth = "token"
	elif role_id and secret_id:
		auth = "approle"

	namespace = clean_str(get("VAULT_NAMESPACE") or get("FERUM_VAULT_NAMESPACE"))
	verify = _vault_verify_param(get)
	cert = _vault_client_cert(get)

	timeout_seconds = parse_int(get("VAULT_TIMEOUT_SECONDS") or get("FERUM_VAULT_TIMEOUT_SECONDS")) or 20
	cache_ttl_seconds = (
		parse_int(get("VAULT_CACHE_TTL_SECONDS") or get("FERUM_VAULT_CACHE_TTL_SECONDS")) or 60
	)

	return VaultConfig(
		addr=str(addr).rstrip("/"),
		mount=str(mount).strip().strip("/"),
		path=str(path).strip().strip("/"),
		auth=auth,
		token=token,
		role_id=role_id,
		secret_id=secret_id,
		namespace=namespace,
		verify=verify,
		cert=cert,
		timeout_seconds=timeout_seconds,
		cache_ttl_seconds=max(5, cache_ttl_seconds),
	)


class VaultClient:
	def __init__(self, config: VaultConfig, *, session: requests.Session | None = None):
		self._config = config
		self._session = session or requests.Session()

		self._token: str | None = config.token
		self._token_expires_at: float | None = None

		self._cache_data: dict[str, Any] | None = None
		self._cache_at: float | None = None

	@property
	def config(self) -> VaultConfig:
		return self._config

	def _login_approle(self) -> str:
		if not self._config.role_id or not self._config.secret_id:
			raise VaultError("Missing VAULT_ROLE_ID/VAULT_SECRET_ID (AppRole auth)")

		url = f"{self._config.addr}/v1/auth/approle/login"
		resp = self._session.post(
			url,
			json={"role_id": self._config.role_id, "secret_id": self._config.secret_id},
			timeout=self._config.timeout_seconds,
			verify=self._config.verify,
			cert=self._config.cert,
			headers=_vault_headers(token=None, namespace=self._config.namespace),
		)
		resp.raise_for_status()
		payload = resp.json() if resp.content else {}

		auth = payload.get("auth") if isinstance(payload, dict) else None
		token = (auth or {}).get("client_token") if isinstance(auth, dict) else None
		token = clean_str(token)
		if not token:
			raise VaultError("AppRole login succeeded but no client_token returned")

		lease = (auth or {}).get("lease_duration") if isinstance(auth, dict) else None
		lease_seconds = parse_int(lease)
		if lease_seconds and lease_seconds > 0:
			# refresh a bit earlier than expiry
			self._token_expires_at = time.monotonic() + max(0, lease_seconds - 30)
		else:
			self._token_expires_at = time.monotonic() + 300

		return token

	def _get_token(self) -> str | None:
		if self._config.auth == "missing":
			return None

		if self._config.auth == "token":
			return self._config.token

		if self._token and self._token_expires_at and time.monotonic() < self._token_expires_at:
			return self._token

		self._token = self._login_approle()
		return self._token

	def sys_health(self) -> dict[str, Any]:
		"""Call Vault `/v1/sys/health` and return a non-secret summary."""
		url = f"{self._config.addr}/v1/sys/health"
		resp = self._session.get(
			url,
			timeout=self._config.timeout_seconds,
			verify=self._config.verify,
			cert=self._config.cert,
			headers=_vault_headers(token=None, namespace=self._config.namespace),
		)

		payload: dict[str, Any] = {}
		try:
			payload = resp.json() if resp.content else {}
		except Exception:
			payload = {}

		return {
			"ok": resp.status_code == 200,
			"status_code": resp.status_code,
			"sealed": payload.get("sealed") if isinstance(payload, dict) else None,
			"initialized": payload.get("initialized") if isinstance(payload, dict) else None,
			"version": payload.get("version") if isinstance(payload, dict) else None,
		}

	def _read_kv_uncached(self) -> dict[str, Any]:
		token = self._get_token()
		headers = _vault_headers(token=token, namespace=self._config.namespace)

		# Prefer KV v2: /v1/<mount>/data/<path>
		url_v2 = f"{self._config.addr}/v1/{self._config.mount}/data/{self._config.path}"
		resp = self._session.get(
			url_v2,
			headers=headers,
			timeout=self._config.timeout_seconds,
			verify=self._config.verify,
			cert=self._config.cert,
		)
		if resp.status_code == 404:
			url_v1 = f"{self._config.addr}/v1/{self._config.mount}/{self._config.path}"
			resp = self._session.get(
				url_v1,
				headers=headers,
				timeout=self._config.timeout_seconds,
				verify=self._config.verify,
				cert=self._config.cert,
			)

		resp.raise_for_status()
		payload = resp.json() if resp.content else {}
		if not isinstance(payload, dict):
			raise VaultError("Vault KV response is not a JSON object")

		# KV v2: payload.data.data
		if isinstance(payload.get("data"), dict) and isinstance(payload["data"].get("data"), dict):
			return payload["data"]["data"]

		# KV v1: payload.data
		if isinstance(payload.get("data"), dict):
			return payload["data"]

		raise VaultError("Vault KV response does not contain data")

	def read_kv(self, *, force_refresh: bool = False) -> dict[str, Any]:
		if not force_refresh and self._cache_data is not None and self._cache_at is not None:
			if (time.monotonic() - self._cache_at) < float(self._config.cache_ttl_seconds):
				return self._cache_data

		data = self._read_kv_uncached()
		self._cache_data = data
		self._cache_at = time.monotonic()
		return data

	def write_kv(self, updates: dict[str, Any], *, merge: bool = True) -> None:
		"""Write KV secrets (KV v2 preferred), optionally merging with existing keys."""
		updates = {str(k): v for k, v in (updates or {}).items() if k and v is not None}
		if not updates:
			return

		token = self._get_token()
		headers = _vault_headers(token=token, namespace=self._config.namespace)

		payload_updates = updates
		if merge:
			try:
				existing = self.read_kv(force_refresh=True) or {}
			except Exception:
				existing = {}
			if isinstance(existing, dict):
				merged = dict(existing)
				merged.update(payload_updates)
				payload_updates = merged

		# Try KV v2 first.
		url_v2 = f"{self._config.addr}/v1/{self._config.mount}/data/{self._config.path}"
		resp = self._session.post(
			url_v2,
			headers=headers,
			json={"data": payload_updates},
			timeout=self._config.timeout_seconds,
			verify=self._config.verify,
			cert=self._config.cert,
		)

		if resp.status_code == 404:
			# Fallback KV v1.
			url_v1 = f"{self._config.addr}/v1/{self._config.mount}/{self._config.path}"
			resp = self._session.post(
				url_v1,
				headers=headers,
				json=payload_updates,
				timeout=self._config.timeout_seconds,
				verify=self._config.verify,
				cert=self._config.cert,
			)

		resp.raise_for_status()
		# Invalidate cache.
		self._cache_data = None
		self._cache_at = None
