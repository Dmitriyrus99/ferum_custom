from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv


logger = logging.getLogger(__name__)


async def _run_forever() -> None:
	# Load `.env` explicitly (python-dotenv's auto-discovery can fail in some runtimes).
	dotenv_path = os.getenv("DOTENV_PATH") or os.getenv("FERUM_DOTENV_PATH") or str(Path.cwd() / ".env")
	load_dotenv(dotenv_path=dotenv_path, override=False)

	token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("FERUM_TELEGRAM_BOT_TOKEN")
	if not token:
		logger.info("TELEGRAM_BOT_TOKEN is not set; telegram bot polling is disabled.")
		return

	# Import after loading env, because backend.config reads env at import time.
	from backend.bot import telegram_bot  # noqa: PLC0415

	backoff_seconds = 5
	while True:
		try:
			await telegram_bot.main()
			# If polling stops gracefully, do not spin/restart.
			logger.info("Telegram bot polling stopped.")
			return
		except Exception:
			logger.exception("Telegram bot crashed; retrying in %ss", backoff_seconds)
			await asyncio.sleep(backoff_seconds)


def main() -> None:
	logging.basicConfig(level=logging.INFO)
	asyncio.run(_run_forever())


if __name__ == "__main__":
	main()
