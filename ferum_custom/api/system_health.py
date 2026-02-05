from __future__ import annotations

import subprocess

import frappe
from frappe import _
from frappe.utils import now_datetime

from ferum_custom.config.settings import get_settings
from ferum_custom.config.validation import validate_security


def _has_role(role: str, user: str | None = None) -> bool:
	user = user or frappe.session.user
	try:
		return role in set(frappe.get_roles(user))
	except Exception:
		return False


def _require_system_manager() -> None:
	if frappe.session.user == "Guest" or not _has_role("System Manager"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _wkhtmltopdf_status() -> dict:
	try:
		cp = subprocess.run(
			["wkhtmltopdf", "--version"],
			capture_output=True,
			text=True,
			check=False,
			timeout=5,
		)
	except FileNotFoundError:
		return {"installed": False}
	except Exception:
		return {"installed": False}

	out = (cp.stdout or "").strip() or (cp.stderr or "").strip()
	return {"installed": cp.returncode == 0, "version": out or None}


def _telegram_bot_config_status() -> dict:
	settings = get_settings()
	token = settings.get("FERUM_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
	mode = (settings.get("FERUM_TELEGRAM_MODE", "MODE") or "polling").strip().lower()

	frappe_url = settings.get("FERUM_FRAPPE_BASE_URL", "ERP_API_URL")
	api_key = settings.get("FERUM_FRAPPE_API_KEY", "ERP_API_KEY")
	api_secret = settings.get("FERUM_FRAPPE_API_SECRET", "ERP_API_SECRET")

	return {
		"configured": bool(token),
		"mode": mode,
		"frappe_api_configured": bool(frappe_url and api_key and api_secret),
	}


def _fastapi_config_status() -> dict:
	settings = get_settings()
	base_url = settings.get("FERUM_FASTAPI_BASE_URL", "FERUM_FASTAPI_BACKEND_URL", "FASTAPI_BACKEND_URL")
	token = settings.get("FERUM_FASTAPI_AUTH_TOKEN", "FASTAPI_AUTH_TOKEN")
	return {"configured": bool(base_url and token)}


def _vault_config_status() -> dict:
	settings = get_settings()
	cfg = settings.vault_config()
	client = settings.vault_client()

	out = {
		"configured": bool(cfg and cfg.auth != "missing"),
		"auth": getattr(cfg, "auth", None) if cfg else "missing",
	}

	if not client:
		return out

	try:
		out["health"] = client.sys_health()
	except Exception as exc:
		out["health"] = {"ok": False, "error": str(exc) or "vault_health_failed"}

	return out


@frappe.whitelist()
@frappe.read_only()
def status() -> dict:
	"""Return non-secret configuration health summary for integrations."""
	_require_system_manager()

	out: dict = {
		"ok": True,
		"generated_at": now_datetime().isoformat(),
		"wkhtmltopdf": _wkhtmltopdf_status(),
		"telegram_bot": _telegram_bot_config_status(),
		"fastapi": _fastapi_config_status(),
		"vault": _vault_config_status(),
		"security_validation": validate_security(),
	}

	try:
		from ferum_custom.api.project_drive import check_drive_config

		out["google_drive"] = check_drive_config()
	except Exception:
		out["google_drive"] = {"ok": False, "error": _("Failed to check Google Drive config.")}

	return out
