from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ferum_custom.config.dotenv import load_dotenv_once
from ferum_custom.config.types import clean_str, is_truthy, parse_float, parse_int, parse_int_set
from ferum_custom.config.vault import VaultClient, VaultConfig, vault_config_from_getter


@dataclass(frozen=True)
class SettingSpec:
	key: str
	aliases: tuple[str, ...] = ()
	secret: bool = False

	@property
	def all_keys(self) -> tuple[str, ...]:
		return (self.key, *self.aliases)


FERUM_TELEGRAM_BOT_TOKEN = SettingSpec(
	key="FERUM_TELEGRAM_BOT_TOKEN",
	aliases=("TELEGRAM_BOT_TOKEN", "ferum_telegram_bot_token"),
	secret=True,
)

FERUM_TELEGRAM_WEBHOOK_SECRET = SettingSpec(
	key="FERUM_TELEGRAM_WEBHOOK_SECRET",
	aliases=("TELEGRAM_WEBHOOK_SECRET",),
	secret=True,
)

FERUM_FASTAPI_BASE_URL = SettingSpec(
	key="FERUM_FASTAPI_BASE_URL",
	aliases=(
		"FERUM_FASTAPI_BACKEND_URL",
		"FASTAPI_BACKEND_URL",
		"ferum_fastapi_base_url",
		"ferum_fastapi_backend_url",
	),
)

FERUM_FASTAPI_AUTH_TOKEN = SettingSpec(
	key="FERUM_FASTAPI_AUTH_TOKEN",
	aliases=("FASTAPI_AUTH_TOKEN", "ferum_fastapi_auth_token"),
	secret=True,
)

FERUM_FRAPPE_BASE_URL = SettingSpec(key="FERUM_FRAPPE_BASE_URL", aliases=("ERP_API_URL",))
FERUM_FRAPPE_API_KEY = SettingSpec(key="FERUM_FRAPPE_API_KEY", aliases=("ERP_API_KEY",), secret=True)
FERUM_FRAPPE_API_SECRET = SettingSpec(key="FERUM_FRAPPE_API_SECRET", aliases=("ERP_API_SECRET",), secret=True)

FERUM_GOOGLE_DRIVE_ROOT_FOLDER_ID = SettingSpec(
	key="FERUM_GOOGLE_DRIVE_ROOT_FOLDER_ID",
	aliases=(
		"FERUM_GOOGLE_DRIVE_FOLDER_ID",
		"GOOGLE_DRIVE_FOLDER_ID",
		"google_drive_folder_id",
		"ferum_google_drive_folder_id",
	),
)

FERUM_GOOGLE_SERVICE_ACCOUNT_JSON = SettingSpec(
	key="FERUM_GOOGLE_SERVICE_ACCOUNT_JSON",
	aliases=(
		"FERUM_GOOGLE_DRIVE_SERVICE_ACCOUNT_KEY_PATH",
		"GOOGLE_DRIVE_SERVICE_ACCOUNT_KEY_PATH",
		"google_drive_service_account_key_path",
	),
	secret=True,
)

SENTRY_DSN = SettingSpec(key="SENTRY_DSN", aliases=("sentry_dsn",), secret=True)

FERUM_JWT_SECRET = SettingSpec(
	key="FERUM_JWT_SECRET",
	aliases=(
		"SECRET_KEY",  # backend compatibility
		"JWT_SECRET",
		"ferum_jwt_secret",
	),
	secret=True,
)


def _safe_get_frappe_conf(key: str) -> Any:
	if "frappe" not in sys.modules:
		return None
	try:
		import frappe
	except Exception:
		return None

	try:
		conf = getattr(frappe, "conf", None)
		if conf is None:
			return None
		return conf.get(key)
	except Exception:
		return None


def _safe_get_frappe_settings_value(key: str) -> str | None:
	"""Backwards-compatible bridge: read from `Ferum Custom Settings` single DocType."""
	if "frappe" not in sys.modules:
		return None
	try:
		import frappe
	except Exception:
		return None

	if not getattr(frappe, "db", None):
		return None

	# Map common env-style keys to DocType fieldnames.
	field_map: dict[str, tuple[str, bool]] = {
		"FERUM_TELEGRAM_BOT_TOKEN": ("telegram_bot_token", True),
		"TELEGRAM_BOT_TOKEN": ("telegram_bot_token", True),
		"FERUM_TELEGRAM_WEBHOOK_SECRET": ("telegram_webhook_secret", True),
		"TELEGRAM_WEBHOOK_SECRET": ("telegram_webhook_secret", True),
		"FERUM_TELEGRAM_DEFAULT_CHAT_ID": ("telegram_default_chat_id", False),
		"FERUM_TELEGRAM_ALLOWED_CHAT_IDS": ("telegram_allowed_chat_ids", False),
		"FERUM_GOOGLE_DRIVE_ROOT_FOLDER_ID": ("google_drive_root_folder_id", False),
		"FERUM_GOOGLE_DRIVE_FOLDER_ID": ("google_drive_root_folder_id", False),
		"SENTRY_DSN": ("sentry_dsn", False),
		"FERUM_JWT_SECRET": ("jwt_secret", True),
	}

	if key not in field_map:
		return None

	fieldname, is_password = field_map[key]
	try:
		doc = frappe.get_cached_doc("Ferum Custom Settings")
	except Exception:
		return None

	try:
		if is_password:
			return clean_str(doc.get_password(fieldname))
		return clean_str(getattr(doc, fieldname, None))
	except Exception:
		return None


class Settings:
	"""Unified typed settings layer.

	Priority order (first non-empty wins):
	1) `frappe.conf`
	2) `os.environ`
	3) Vault KV (if configured)
	4) `Ferum Custom Settings` single DocType
	"""

	def __init__(self):
		load_dotenv_once()
		self._vault: VaultClient | None = None
		self._vault_config: VaultConfig | None = None
		self._vault_init_error: str | None = None
		self._vault_failed_until: float | None = None
		self._vault_failure_backoff_seconds = (
			parse_int(
				os.getenv("VAULT_FAILURE_BACKOFF_SECONDS") or os.getenv("FERUM_VAULT_FAILURE_BACKOFF_SECONDS")
			)
			or 30
		)

		self._init_vault()

	def _bootstrap_get(self, key: str) -> Any:
		# NOTE: Vault bootstrap must not depend on Vault itself.
		val = _safe_get_frappe_conf(key)
		if val is not None:
			return val
		return os.getenv(key)

	def _init_vault(self) -> None:
		try:
			cfg = vault_config_from_getter(self._bootstrap_get)
		except Exception as exc:
			self._vault_init_error = str(exc) or "vault_config_error"
			return

		if not cfg or cfg.auth == "missing":
			return

		self._vault_config = cfg
		try:
			self._vault = VaultClient(cfg)
		except Exception as exc:
			self._vault_init_error = str(exc) or "vault_init_failed"
			self._vault = None

	def vault_client(self) -> VaultClient | None:
		return self._vault

	def vault_config(self) -> VaultConfig | None:
		return self._vault_config

	def vault_bootstrap_error(self) -> str | None:
		return self._vault_init_error

	def _providers(self) -> tuple[Callable[[str], Any], ...]:
		return (
			_safe_get_frappe_conf,
			os.getenv,
			self._vault_get,
			_safe_get_frappe_settings_value,
		)

	def _vault_get(self, key: str) -> Any:
		if not self._vault:
			return None
		if self._vault_failed_until and time.monotonic() < self._vault_failed_until:
			return None
		try:
			data = self._vault.read_kv()
		except Exception:
			self._vault_failed_until = time.monotonic() + float(max(5, self._vault_failure_backoff_seconds))
			return None
		if not isinstance(data, dict):
			return None
		return data.get(key)

	def get(self, *keys: str, default: str | None = None) -> str | None:
		aliases = [k for k in keys if clean_str(k)]
		for provider in self._providers():
			for key in aliases:
				val = provider(key)
				val = clean_str(val)
				if val:
					return val
		return default

	def get_bool(self, *keys: str, default: bool = False) -> bool:
		value = self.get(*keys)
		if value is None:
			return default
		return is_truthy(value)

	def get_int(self, *keys: str, default: int | None = None) -> int | None:
		value = self.get(*keys)
		return parse_int(value) if value is not None else default

	def get_float(self, *keys: str, default: float | None = None) -> float | None:
		value = self.get(*keys)
		return parse_float(value) if value is not None else default

	def get_int_set(self, *keys: str, default: set[int] | None = None) -> set[int] | None:
		value = self.get(*keys)
		return parse_int_set(value) if value is not None else default

	def get_spec(self, spec: SettingSpec, *, default: str | None = None) -> str | None:
		return self.get(*spec.all_keys, default=default)

	def has_spec(self, spec: SettingSpec) -> bool:
		return bool(self.get_spec(spec))


_SETTINGS: Settings | None = None


def get_settings(*, refresh: bool = False) -> Settings:
	global _SETTINGS
	if refresh or _SETTINGS is None:
		_SETTINGS = Settings()
	return _SETTINGS


def reset_settings_cache() -> None:
	global _SETTINGS
	_SETTINGS = None
