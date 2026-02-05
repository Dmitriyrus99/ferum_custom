#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Any

import requests

_ASSIGN_RE = re.compile(
	r"^(?P<prefix>\s*(?:export\s+)?)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*)$"
)


def _parse_bool(raw: str | None) -> bool:
	raw = str(raw or "").strip().lower()
	return raw in {"1", "true", "yes", "on"}


def _load_dotenv_file(path: Path) -> None:
	"""Best-effort dotenv loader (without external deps). Only sets missing os.environ keys."""
	if not path.exists():
		return
	for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
		line = line.strip()
		if not line or line.startswith("#"):
			continue
		m = _ASSIGN_RE.match(line)
		if not m:
			continue
		key = m.group("key")
		value = (m.group("value") or "").strip()
		if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
			value = value[1:-1]
		if key and key not in os.environ:
			os.environ[key] = value


def _format_env_value(value: str) -> str:
	"""Format a value for .env safely as a single line."""
	value = str(value or "")
	# Avoid multi-line secrets in .env; keep deterministic single-line.
	value = value.replace("\r\n", "\n").replace("\r", "\n")
	if "\n" in value:
		value = value.replace("\n", "\\n")

	needs_quotes = any(ch.isspace() for ch in value) or any(ch in value for ch in ["#", '"', "'"])
	if not needs_quotes and value != "":
		return value

	escaped = value.replace("\\", "\\\\").replace('"', '\\"')
	return f'"{escaped}"'


class VaultError(RuntimeError):
	pass


def _vault_session() -> requests.Session:
	s = requests.Session()
	# Keep default adapters/timeouts; just reuse connections.
	return s


def _vault_verify_param() -> bool | str:
	if _parse_bool(os.getenv("VAULT_SKIP_VERIFY") or os.getenv("FERUM_VAULT_SKIP_VERIFY")):
		return False
	ca = os.getenv("VAULT_CACERT") or os.getenv("FERUM_VAULT_CACERT") or os.getenv("VAULT_CA_CERT")
	return str(ca).strip() if ca else True


def _vault_client_cert() -> str | tuple[str, str] | None:
	cert = (os.getenv("VAULT_CLIENT_CERT") or os.getenv("FERUM_VAULT_CLIENT_CERT") or "").strip()
	key = (os.getenv("VAULT_CLIENT_KEY") or os.getenv("FERUM_VAULT_CLIENT_KEY") or "").strip()
	if cert and key:
		return cert, key
	if cert:
		return cert
	return None


def _vault_headers(*, token: str | None) -> dict[str, str]:
	headers: dict[str, str] = {}
	namespace = (os.getenv("VAULT_NAMESPACE") or os.getenv("FERUM_VAULT_NAMESPACE") or "").strip()
	if namespace:
		headers["X-Vault-Namespace"] = namespace
	if token:
		headers["X-Vault-Token"] = token
	return headers


def _vault_addr() -> str:
	addr = (os.getenv("VAULT_ADDR") or os.getenv("FERUM_VAULT_ADDR") or "").strip()
	if not addr:
		raise VaultError("Missing VAULT_ADDR")
	return addr.rstrip("/")


def _vault_login_approle(session: requests.Session, *, addr: str) -> str:
	role_id = (os.getenv("VAULT_ROLE_ID") or os.getenv("FERUM_VAULT_ROLE_ID") or "").strip()
	secret_id = (os.getenv("VAULT_SECRET_ID") or os.getenv("FERUM_VAULT_SECRET_ID") or "").strip()
	if not role_id or not secret_id:
		raise VaultError("Missing VAULT_ROLE_ID/VAULT_SECRET_ID (AppRole auth)")

	url = f"{addr}/v1/auth/approle/login"
	verify = _vault_verify_param()
	cert = _vault_client_cert()
	resp = session.post(
		url,
		json={"role_id": role_id, "secret_id": secret_id},
		timeout=20,
		verify=verify,
		cert=cert,
	)
	resp.raise_for_status()
	payload = resp.json() if resp.content else {}
	token = (
		(payload.get("auth") or {}).get("client_token")
		if isinstance(payload, dict) and isinstance(payload.get("auth"), dict)
		else None
	)
	token = str(token or "").strip()
	if not token:
		raise VaultError("AppRole login succeeded but no client_token returned")
	return token


def _vault_token(session: requests.Session, *, addr: str) -> str:
	token = (os.getenv("VAULT_TOKEN") or os.getenv("FERUM_VAULT_TOKEN") or "").strip()
	if token:
		return token
	return _vault_login_approle(session, addr=addr)


def _kv_mount_path() -> tuple[str, str]:
	mount = (os.getenv("VAULT_MOUNT") or os.getenv("FERUM_VAULT_MOUNT") or "secret").strip().strip("/")
	path = (os.getenv("VAULT_PATH") or os.getenv("FERUM_VAULT_PATH") or "").strip().strip("/")
	if not path:
		raise VaultError("Missing VAULT_PATH")
	return mount, path


def _vault_read_kv(
	session: requests.Session, *, addr: str, token: str, mount: str, path: str
) -> dict[str, Any]:
	verify = _vault_verify_param()
	cert = _vault_client_cert()
	headers = _vault_headers(token=token)

	# Prefer KV v2: /v1/<mount>/data/<path>
	url_v2 = f"{addr}/v1/{mount}/data/{path}"
	resp = session.get(url_v2, headers=headers, timeout=20, verify=verify, cert=cert)
	if resp.status_code == 404:
		# Fallback to KV v1: /v1/<mount>/<path>
		url_v1 = f"{addr}/v1/{mount}/{path}"
		resp = session.get(url_v1, headers=headers, timeout=20, verify=verify, cert=cert)
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


def _render_env(
	*,
	template_path: Path,
	output_path: Path,
	secrets: dict[str, Any],
	keep_existing: bool,
) -> tuple[int, list[str]]:
	template_lines = template_path.read_text(encoding="utf-8", errors="ignore").splitlines()
	out_lines: list[str] = []
	replaced = 0
	missing: list[str] = []

	for line in template_lines:
		m = _ASSIGN_RE.match(line.strip())
		if not m:
			out_lines.append(line)
			continue

		key = m.group("key")
		prefix = m.group("prefix") or ""
		current_value = (m.group("value") or "").strip()

		if key in secrets and secrets[key] is not None:
			out_lines.append(f"{prefix}{key}={_format_env_value(str(secrets[key]))}")
			replaced += 1
			continue

		if keep_existing and current_value != "":
			out_lines.append(line)
		else:
			out_lines.append(f"{prefix}{key}=")
			missing.append(key)

	output_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
	return replaced, missing


def main() -> int:
	parser = argparse.ArgumentParser(description="Render bench .env from Hashicorp Vault KV secrets.")
	parser.add_argument("--template", default=".env.example", help="Path to template dotenv (.env.example).")
	parser.add_argument("--output", default=".env", help="Output dotenv path (.env).")
	parser.add_argument(
		"--dotenv",
		default=None,
		help="Optional dotenv path to load into environment before contacting Vault (e.g. .env).",
	)
	parser.add_argument(
		"--keep-existing",
		action="store_true",
		help="Keep non-empty values from template if key not found in Vault.",
	)
	parser.add_argument(
		"--dry-run",
		action="store_true",
		help="Do not write output; only print summary (never prints secret values).",
	)
	args = parser.parse_args()

	template_path = Path(args.template).expanduser().resolve()
	output_path = Path(args.output).expanduser().resolve()
	if not template_path.exists():
		raise SystemExit(f"Template not found: {template_path}")

	if args.dotenv:
		_load_dotenv_file(Path(args.dotenv).expanduser().resolve())

	session = _vault_session()
	addr = _vault_addr()
	token = _vault_token(session, addr=addr)
	mount, path = _kv_mount_path()
	secrets = _vault_read_kv(session, addr=addr, token=token, mount=mount, path=path)

	if args.dry_run:
		# Render to nowhere: just count replacements/missing.
		replaced, missing = _render_env(
			template_path=template_path,
			output_path=Path(os.devnull),
			secrets=secrets,
			keep_existing=bool(args.keep_existing),
		)
		# Never print secret values.
		print(f"template={template_path}")
		print(f"vault_addr={addr}")
		print(f"vault_kv={mount}/{path}")
		print(f"keys_from_vault={len(secrets)}")
		print(f"replaced={replaced}")
		print(f"missing={len(missing)}")
		return 0

	replaced, missing = _render_env(
		template_path=template_path,
		output_path=output_path,
		secrets=secrets,
		keep_existing=bool(args.keep_existing),
	)

	print(f"Wrote: {output_path}")
	print(f"replaced={replaced} missing={len(missing)}")
	if missing:
		print("Missing keys (not found in Vault and empty in template):")
		for k in missing:
			print(f"- {k}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
