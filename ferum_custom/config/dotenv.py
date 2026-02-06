from __future__ import annotations

import os
import re
from pathlib import Path

_DOTENV_LOADED = False
_DOTENV_PATH: str | None = None

_ASSIGN_RE = re.compile(
	r"^(?P<prefix>\s*(?:export\s+)?)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*)$"
)


def find_dotenv_path() -> Path | None:
	"""Find bench `.env` path (best effort).

	Order:
	- `DOTENV_PATH` / `FERUM_DOTENV_PATH` env override
	- `.env` in current working directory
	- `.env` up the directory tree (up to 10 levels)
	"""
	explicit = (os.getenv("DOTENV_PATH") or os.getenv("FERUM_DOTENV_PATH") or "").strip()
	if explicit:
		path = Path(explicit).expanduser()
		return path

	cwd_env = Path.cwd() / ".env"
	if cwd_env.exists():
		return cwd_env

	for parent in Path(__file__).resolve().parents[:10]:
		candidate = parent / ".env"
		if candidate.exists():
			return candidate

	return None


def _load_dotenv_fallback(path: Path) -> None:
	"""Minimal dotenv parser (no external deps), only sets missing env vars."""
	if not path.exists():
		return
	for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
		line = line.strip()
		if not line or line.startswith("#"):
			continue
		match = _ASSIGN_RE.match(line)
		if not match:
			continue
		key = match.group("key")
		value = (match.group("value") or "").strip()
		if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
			value = value[1:-1]
		if key and key not in os.environ:
			os.environ[key] = value


def load_dotenv_once() -> str | None:
	"""Load dotenv once per-process (never overrides existing env vars)."""
	global _DOTENV_LOADED, _DOTENV_PATH
	if _DOTENV_LOADED:
		return _DOTENV_PATH

	_DOTENV_LOADED = True
	path = find_dotenv_path()
	_DOTENV_PATH = str(path) if path else None
	if not path:
		return None

	try:
		from dotenv import load_dotenv

		load_dotenv(dotenv_path=str(path), override=False)
	except Exception:
		_load_dotenv_fallback(path)

	return _DOTENV_PATH


def loaded_dotenv_path() -> str | None:
	return _DOTENV_PATH
