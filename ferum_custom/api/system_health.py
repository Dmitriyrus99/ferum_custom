from __future__ import annotations

import os
import subprocess
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import now_datetime

_DOTENV_LOADED = False


def _ensure_dotenv_loaded() -> None:
	"""Load bench `.env` for long-running processes where env vars may not be passed explicitly."""
	global _DOTENV_LOADED
	if _DOTENV_LOADED:
		return
	_DOTENV_LOADED = True
	try:
		from dotenv import load_dotenv  # type: ignore
	except Exception:
		return

	for parent in Path(__file__).resolve().parents[:8]:
		candidate = parent / ".env"
		if candidate.exists():
			load_dotenv(dotenv_path=str(candidate), override=False)
			return


def _get_conf(key: str) -> str | None:
	_ensure_dotenv_loaded()
	val = frappe.conf.get(key) if hasattr(frappe, "conf") else None
	if val is None:
		val = os.getenv(key)
	if val is None:
		return None
	val = str(val).strip()
	return val or None


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
	token = _get_conf("FERUM_TELEGRAM_BOT_TOKEN") or _get_conf("TELEGRAM_BOT_TOKEN")
	mode = (_get_conf("FERUM_TELEGRAM_MODE") or _get_conf("MODE") or "polling").strip().lower()

	frappe_url = _get_conf("FERUM_FRAPPE_BASE_URL") or _get_conf("ERP_API_URL")
	api_key = _get_conf("FERUM_FRAPPE_API_KEY") or _get_conf("ERP_API_KEY")
	api_secret = _get_conf("FERUM_FRAPPE_API_SECRET") or _get_conf("ERP_API_SECRET")

	return {
		"configured": bool(token),
		"mode": mode,
		"frappe_api_configured": bool(frappe_url and api_key and api_secret),
	}


def _fastapi_config_status() -> dict:
	base_url = (
		_get_conf("FERUM_FASTAPI_BASE_URL")
		or _get_conf("FERUM_FASTAPI_BACKEND_URL")
		or _get_conf("FASTAPI_BACKEND_URL")
	)
	token = _get_conf("FERUM_FASTAPI_AUTH_TOKEN") or _get_conf("FASTAPI_AUTH_TOKEN")
	return {"configured": bool(base_url and token)}


def _vault_config_status() -> dict:
	addr = _get_conf("VAULT_ADDR") or _get_conf("FERUM_VAULT_ADDR")
	mount = _get_conf("VAULT_MOUNT") or _get_conf("FERUM_VAULT_MOUNT")
	path = _get_conf("VAULT_PATH") or _get_conf("FERUM_VAULT_PATH")
	token = _get_conf("VAULT_TOKEN") or _get_conf("FERUM_VAULT_TOKEN")
	role_id = _get_conf("VAULT_ROLE_ID") or _get_conf("FERUM_VAULT_ROLE_ID")
	secret_id = _get_conf("VAULT_SECRET_ID") or _get_conf("FERUM_VAULT_SECRET_ID")

	auth = "token" if token else ("approle" if (role_id and secret_id) else "missing")
	return {
		"configured": bool(addr and mount and path and auth != "missing"),
		"auth": auth,
	}


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
	}

	try:
		from ferum_custom.api.project_drive import check_drive_config

		out["google_drive"] = check_drive_config()
	except Exception:
		out["google_drive"] = {"ok": False, "error": _("Failed to check Google Drive config.")}

	return out
