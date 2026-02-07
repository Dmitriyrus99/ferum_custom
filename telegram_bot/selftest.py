from __future__ import annotations

"""Compatibility self-test runner for the Telegram bot.

Canonical implementation lives under `ferum_custom.integrations.telegram_bot`.
"""

from ferum_custom.integrations.telegram_bot.selftest import main

if __name__ == "__main__":
	raise SystemExit(main())
