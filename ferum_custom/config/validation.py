from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

from ferum_custom.config.dotenv import loaded_dotenv_path
from ferum_custom.config.settings import FERUM_TELEGRAM_BOT_TOKEN, get_settings
from ferum_custom.config.types import clean_str, is_truthy


@dataclass(frozen=True)
class ValidationIssue:
	code: str
	severity: str  # P0/P1/P2/P3
	message: str


def _file_mode_safe(path: Path) -> bool | None:
	try:
		mode = path.stat().st_mode
	except Exception:
		return None
	# Group/other readable is usually a mistake for `.env` in production.
	return (mode & 0o077) == 0


def validate_security() -> dict:
	"""Return non-secret validation summary for ops / health checks."""
	settings = get_settings()
	issues: list[ValidationIssue] = []

	dotenv_path = clean_str(loaded_dotenv_path())
	if dotenv_path:
		safe = _file_mode_safe(Path(dotenv_path))
		if safe is False:
			issues.append(
				ValidationIssue(
					code="dotenv.permissions",
					severity="P1",
					message=f"Dotenv file permissions are too open: {dotenv_path}. Recommend chmod 600.",
				)
			)

	vault_addr = settings.get("VAULT_ADDR", "FERUM_VAULT_ADDR")
	if vault_addr and vault_addr.startswith("http://"):
		issues.append(
			ValidationIssue(
				code="vault.insecure_transport",
				severity="P0",
				message="Vault is configured over HTTP. Use HTTPS + TLS verification.",
			)
		)

	if is_truthy(os.getenv("VAULT_SKIP_VERIFY") or os.getenv("FERUM_VAULT_SKIP_VERIFY")):
		issues.append(
			ValidationIssue(
				code="vault.skip_verify",
				severity="P1",
				message="Vault TLS verification is disabled (VAULT_SKIP_VERIFY). Use CA bundle instead.",
			)
		)

	# Telegram bot token should never be missing in environments where bot is enabled.
	if not settings.has_spec(FERUM_TELEGRAM_BOT_TOKEN):
		issues.append(
			ValidationIssue(
				code="telegram.missing_token",
				severity="P2",
				message="Telegram bot token is not configured (FERUM_TELEGRAM_BOT_TOKEN).",
			)
		)

	jwt_secret = settings.get("FERUM_JWT_SECRET", "SECRET_KEY")
	if not jwt_secret:
		issues.append(
			ValidationIssue(
				code="backend.jwt_secret.missing",
				severity="P1",
				message="JWT secret is not configured (FERUM_JWT_SECRET / SECRET_KEY).",
			)
		)
	elif jwt_secret == "super-secret-key":
		issues.append(
			ValidationIssue(
				code="backend.jwt_secret.insecure_default",
				severity="P0",
				message="JWT secret uses insecure default value; set FERUM_JWT_SECRET / SECRET_KEY.",
			)
		)

	return {
		"ok": not issues,
		"dotenv_path": dotenv_path,
		"issues": [asdict(i) for i in issues],
	}
