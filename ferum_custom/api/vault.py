from __future__ import annotations

from pathlib import Path

import frappe
from frappe import _

from ferum_custom.config.settings import get_settings


def _has_role(role: str, user: str | None = None) -> bool:
	user = user or frappe.session.user
	try:
		return role in set(frappe.get_roles(user))
	except Exception:
		return False


def _require_system_manager() -> None:
	if frappe.session.user == "Guest" or not _has_role("System Manager"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _read_local_file_from_url(file_url: str) -> str | None:
	file_url = str(file_url or "").strip()
	if not file_url:
		return None

	if file_url.startswith("/private/files/"):
		rel = file_url.removeprefix("/private/files/").lstrip("/")
		path = Path(frappe.get_site_path("private", "files", rel))
	elif file_url.startswith("/files/"):
		rel = file_url.removeprefix("/files/").lstrip("/")
		path = Path(frappe.get_site_path("public", "files", rel))
	else:
		return None

	try:
		return path.read_text(encoding="utf-8")
	except Exception:
		return None


def _get_google_service_account_json_from_settings() -> str | None:
	try:
		doc = frappe.get_cached_doc("Ferum Custom Settings")
	except Exception:
		return None

	file_url = str(getattr(doc, "google_service_account_json", "") or "").strip()
	if not file_url:
		return None

	content = _read_local_file_from_url(file_url)
	if not content:
		return None

	# Basic sanity check; do not parse/validate deeply here.
	content = content.strip()
	if not content.startswith("{"):
		return None
	return content


@frappe.whitelist()
@frappe.read_only()
def health() -> dict:
	"""Return Vault non-secret status for operators."""
	_require_system_manager()

	settings = get_settings(refresh=True)
	client = settings.vault_client()
	cfg = settings.vault_config()

	out = {
		"configured": bool(cfg and cfg.auth != "missing"),
		"auth": getattr(cfg, "auth", None) if cfg else "missing",
		"vault_addr": getattr(cfg, "addr", None) if cfg else None,
		"vault_mount": getattr(cfg, "mount", None) if cfg else None,
		"vault_path": getattr(cfg, "path", None) if cfg else None,
		"bootstrap_error": settings.vault_bootstrap_error(),
	}

	if not client:
		return out

	try:
		out["health"] = client.sys_health()
	except Exception as exc:
		out["health"] = {"ok": False, "error": str(exc) or "vault_health_failed"}

	return out


@frappe.whitelist()
def sync_settings_to_vault(*, dry_run: int | bool = 1, only_missing: int | bool = 1) -> dict:
	"""Sync selected settings into Vault KV (idempotent).

	- Never returns secret values.
	- Writes to the configured Vault KV path (`VAULT_MOUNT`/`VAULT_PATH`).
	"""
	_require_system_manager()

	settings = get_settings(refresh=True)
	client = settings.vault_client()
	if not client:
		frappe.throw(_("Vault is not configured."), frappe.ValidationError)

	# Read current values from the `Ferum Custom Settings` single DocType.
	try:
		doc = frappe.get_cached_doc("Ferum Custom Settings")
	except Exception:
		doc = None

	updates: dict[str, str] = {}

	def _maybe_set(key: str, value: str | None) -> None:
		value = str(value or "").strip()
		if not value:
			return
		updates[key] = value

	if doc:
		_maybe_set("FERUM_TELEGRAM_BOT_TOKEN", doc.get_password("telegram_bot_token"))
		_maybe_set("FERUM_TELEGRAM_WEBHOOK_SECRET", doc.get_password("telegram_webhook_secret"))
		_maybe_set("FERUM_JWT_SECRET", doc.get_password("jwt_secret"))
		_maybe_set("SENTRY_DSN", getattr(doc, "sentry_dsn", None))
		_maybe_set("FERUM_GOOGLE_DRIVE_ROOT_FOLDER_ID", getattr(doc, "google_drive_root_folder_id", None))
		_maybe_set("FERUM_TELEGRAM_DEFAULT_CHAT_ID", getattr(doc, "telegram_default_chat_id", None))
		_maybe_set("FERUM_TELEGRAM_ALLOWED_CHAT_IDS", getattr(doc, "telegram_allowed_chat_ids", None))

		sa_json = _get_google_service_account_json_from_settings()
		if sa_json:
			_maybe_set("FERUM_GOOGLE_SERVICE_ACCOUNT_JSON", sa_json)

	# Also migrate relevant env-style keys if present (common for bot/backend).
	_maybe_set("FERUM_FRAPPE_API_KEY", settings.get("FERUM_FRAPPE_API_KEY", "ERP_API_KEY"))
	_maybe_set("FERUM_FRAPPE_API_SECRET", settings.get("FERUM_FRAPPE_API_SECRET", "ERP_API_SECRET"))
	_maybe_set("FERUM_FASTAPI_AUTH_TOKEN", settings.get("FERUM_FASTAPI_AUTH_TOKEN", "FASTAPI_AUTH_TOKEN"))
	_maybe_set("FERUM_JWT_SECRET", settings.get("FERUM_JWT_SECRET", "SECRET_KEY"))

	if not updates:
		return {
			"ok": True,
			"dry_run": bool(int(dry_run)),
			"written": [],
			"skipped": [],
			"message": "Nothing to sync.",
		}

	existing: dict[str, object] = {}
	if bool(int(only_missing)):
		try:
			existing = client.read_kv(force_refresh=True) or {}
		except Exception as exc:
			frappe.throw(_("Failed to read existing Vault KV: {0}").format(exc), frappe.ValidationError)
		if not isinstance(existing, dict):
			existing = {}

	would_write: list[str] = []
	skipped: list[str] = []
	for key in sorted(updates.keys()):
		current = existing.get(key) if isinstance(existing, dict) else None
		if bool(int(only_missing)) and str(current or "").strip():
			skipped.append(key)
			continue
		would_write.append(key)

	if bool(int(dry_run)):
		return {
			"ok": True,
			"dry_run": True,
			"would_write": would_write,
			"skipped": skipped,
			"total_candidates": len(updates),
		}

	try:
		client.write_kv({k: updates[k] for k in would_write}, merge=True)
	except Exception as exc:
		frappe.throw(_("Failed to write Vault KV: {0}").format(exc), frappe.ValidationError)

	return {
		"ok": True,
		"dry_run": False,
		"written": would_write,
		"skipped": skipped,
		"total_candidates": len(updates),
	}
