from __future__ import annotations

import os

import frappe
from frappe.tests.utils import FrappeTestCase

from ferum_custom.config.settings import reset_settings_cache


class TestVaultCutover(FrappeTestCase):
	def test_clear_settings_secrets_only_if_in_vault(self) -> None:
		"""Secrets can be cleared from DB only after confirming Vault has them."""

		doc = frappe.get_doc("Ferum Custom Settings")
		orig = {
			"telegram_bot_token": doc.get_password("telegram_bot_token", raise_exception=False),
			"telegram_webhook_secret": doc.get_password("telegram_webhook_secret", raise_exception=False),
			"jwt_secret": doc.get_password("jwt_secret", raise_exception=False),
			"sentry_dsn": getattr(doc, "sentry_dsn", None),
		}

		vault_env_keys = ["VAULT_ADDR", "VAULT_MOUNT", "VAULT_PATH", "VAULT_TOKEN"]
		orig_env = {k: os.environ.get(k) for k in vault_env_keys}

		class DummyVault:
			def __init__(self, config):
				self._config = config

			def read_kv(self, *, force_refresh: bool = False):
				# Provide only telegram secrets; JWT + Sentry are intentionally missing.
				return {
					"FERUM_TELEGRAM_BOT_TOKEN": "vault_token",
					"FERUM_TELEGRAM_WEBHOOK_SECRET": "vault_secret",
				}

		import ferum_custom.config.settings as settings_module

		orig_vault_client = settings_module.VaultClient
		try:
			# Seed DB with values to clear.
			doc.telegram_bot_token = "db_token"
			doc.telegram_webhook_secret = "db_webhook_secret"
			doc.jwt_secret = "db_jwt_secret"
			doc.sentry_dsn = "https://example.invalid/1"
			doc.save(ignore_permissions=True)

			# Configure Vault bootstrap, but use a dummy client (no network).
			for k in vault_env_keys:
				os.environ.pop(k, None)
			os.environ["VAULT_ADDR"] = "https://vault.example"
			os.environ["VAULT_MOUNT"] = "secret"
			os.environ["VAULT_PATH"] = "ferum/test"
			os.environ["VAULT_TOKEN"] = "token"

			settings_module.VaultClient = DummyVault
			reset_settings_cache()

			from ferum_custom.api.vault import clear_settings_secrets

			# With `only_if_in_vault=1`, only telegram secrets are cleared.
			out = clear_settings_secrets(dry_run=0, only_if_in_vault=1)
			self.assertTrue(out["ok"])
			self.assertFalse(out["dry_run"])

			doc2 = frappe.get_doc("Ferum Custom Settings")
			self.assertIsNone(doc2.get_password("telegram_bot_token", raise_exception=False))
			self.assertIsNone(doc2.get_password("telegram_webhook_secret", raise_exception=False))
			self.assertEqual(doc2.get_password("jwt_secret"), "db_jwt_secret")
			self.assertEqual((doc2.sentry_dsn or "").strip(), "https://example.invalid/1")

			# Without the guard, remaining secrets are cleared too.
			out2 = clear_settings_secrets(dry_run=0, only_if_in_vault=0)
			self.assertTrue(out2["ok"])

			doc3 = frappe.get_doc("Ferum Custom Settings")
			self.assertIsNone(doc3.get_password("jwt_secret", raise_exception=False))
			self.assertEqual((doc3.sentry_dsn or "").strip(), "")

		finally:
			# Restore VaultClient + env.
			settings_module.VaultClient = orig_vault_client
			reset_settings_cache()
			for k, v in orig_env.items():
				if v is None:
					os.environ.pop(k, None)
				else:
					os.environ[k] = v

			# Restore original DB values.
			doc_restore = frappe.get_doc("Ferum Custom Settings")
			doc_restore.telegram_bot_token = orig["telegram_bot_token"] or ""
			doc_restore.telegram_webhook_secret = orig["telegram_webhook_secret"] or ""
			doc_restore.jwt_secret = orig["jwt_secret"] or ""
			doc_restore.sentry_dsn = orig["sentry_dsn"] or ""
			doc_restore.save(ignore_permissions=True)
