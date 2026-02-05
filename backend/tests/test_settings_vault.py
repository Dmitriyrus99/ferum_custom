from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import Mock

import pytest

from ferum_custom.config.settings import get_settings, reset_settings_cache
from ferum_custom.config.vault import VaultClient, VaultConfig


@dataclass
class DummyResponse:
	status_code: int
	payload: Any

	@property
	def content(self) -> bytes:
		return b"{}"

	def json(self) -> Any:
		return self.payload

	def raise_for_status(self) -> None:
		if self.status_code >= 400:
			raise RuntimeError(f"http {self.status_code}")


def test_settings_env_overrides_vault(monkeypatch: pytest.MonkeyPatch) -> None:
	class DummyVault:
		def __init__(self, config: Any):
			self._config = config

		def read_kv(self, *, force_refresh: bool = False) -> dict[str, Any]:
			return {"FERUM_TELEGRAM_BOT_TOKEN": "from_vault"}

	reset_settings_cache()
	monkeypatch.setenv("VAULT_ADDR", "https://vault.example")
	monkeypatch.setenv("VAULT_MOUNT", "secret")
	monkeypatch.setenv("VAULT_PATH", "ferum/test")
	monkeypatch.setenv("VAULT_TOKEN", "token")

	# Vault has token, but env must still win.
	monkeypatch.setenv("FERUM_TELEGRAM_BOT_TOKEN", "from_env")
	monkeypatch.setattr("ferum_custom.config.settings.VaultClient", DummyVault)

	settings = get_settings(refresh=True)
	assert settings.get("FERUM_TELEGRAM_BOT_TOKEN") == "from_env"


def test_settings_vault_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
	class DummyVault:
		def __init__(self, config: Any):
			self._config = config

		def read_kv(self, *, force_refresh: bool = False) -> dict[str, Any]:
			return {"FERUM_FASTAPI_AUTH_TOKEN": "from_vault"}

	reset_settings_cache()
	monkeypatch.delenv("FERUM_FASTAPI_AUTH_TOKEN", raising=False)
	monkeypatch.setenv("VAULT_ADDR", "https://vault.example")
	monkeypatch.setenv("VAULT_MOUNT", "secret")
	monkeypatch.setenv("VAULT_PATH", "ferum/test")
	monkeypatch.setenv("VAULT_TOKEN", "token")
	monkeypatch.setattr("ferum_custom.config.settings.VaultClient", DummyVault)

	settings = get_settings(refresh=True)
	assert settings.get("FERUM_FASTAPI_AUTH_TOKEN") == "from_vault"


def test_vaultclient_read_kv_v2() -> None:
	session = Mock()
	session.get.return_value = DummyResponse(200, {"data": {"data": {"A": "1"}}})

	cfg = VaultConfig(
		addr="https://vault.example",
		mount="secret",
		path="ferum/test",
		auth="token",
		token="t",
		cache_ttl_seconds=999,
	)
	client = VaultClient(cfg, session=session)
	assert client.read_kv() == {"A": "1"}

	# Cached.
	assert client.read_kv() == {"A": "1"}
	assert session.get.call_count == 1


def test_vaultclient_write_kv_merge_preserves_keys() -> None:
	session = Mock()
	session.get.return_value = DummyResponse(200, {"data": {"data": {"A": "old", "B": "keep"}}})
	session.post.return_value = DummyResponse(200, {})

	cfg = VaultConfig(
		addr="https://vault.example",
		mount="secret",
		path="ferum/test",
		auth="token",
		token="t",
		cache_ttl_seconds=0,
	)
	client = VaultClient(cfg, session=session)

	client.write_kv({"A": "new"}, merge=True)

	assert session.post.call_count == 1
	kwargs = session.post.call_args.kwargs
	assert kwargs["json"]["data"]["A"] == "new"
	assert kwargs["json"]["data"]["B"] == "keep"
