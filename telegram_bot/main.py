from __future__ import annotations

"""Compatibility entrypoint for the Telegram bot.

Canonical implementation lives under `ferum_custom.integrations.telegram_bot`.
This wrapper preserves historical run commands like:
`python -m apps.ferum_custom.telegram_bot.main`
"""

from ferum_custom.integrations.telegram_bot.main import main

if __name__ == "__main__":
	main()
