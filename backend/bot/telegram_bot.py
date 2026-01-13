import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING, Any

import httpx

try:
	from aiogram import Bot, Dispatcher, types
	from aiogram.filters import Command, CommandStart
except ImportError:  # pragma: no cover - optional dependency for bot runtime
	Bot = Dispatcher = types = Command = CommandStart = None

if TYPE_CHECKING:
	from aiogram.types import Message
else:
	Message = Any

from ..config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot lazily to allow imports/tests without TELEGRAM_BOT_TOKEN configured.
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN) if Bot and settings.TELEGRAM_BOT_TOKEN else None
dp = Dispatcher() if Dispatcher else None

# Base URL for your FastAPI backend
FASTAPI_BASE_URL = (
	os.getenv("FERUM_FASTAPI_BASE_URL") or os.getenv("FASTAPI_BASE_URL") or "http://localhost:8000/api/v1"
)


def _fastapi_auth_headers() -> dict[str, str]:
	token = os.getenv("FERUM_FASTAPI_AUTH_TOKEN") or os.getenv("FASTAPI_AUTH_TOKEN") or ""
	if not token:
		return {}
	return {"Authorization": f"Bearer {token}"}


if dp and CommandStart:

	@dp.message(CommandStart())
	async def command_start_handler(message: Message) -> None:
		"""This handler receives messages with the `/start` command"""
		await message.answer(f"Hello, {message.from_user.full_name}! I am your Ferum Customizations bot.")

else:

	async def command_start_handler(
		message: Message,
	) -> None:  # pragma: no cover - not used without aiogram
		raise RuntimeError("Aiogram is not installed; Telegram bot handlers are unavailable.")


if dp and Command:

	@dp.message(Command("new_request"))
	async def new_request_handler(message: Message) -> None:
		# This is a simplified example. In a real bot, you'd use FSM (Finite State Machine)
		# to guide the user through providing request details.
		try:
			# Extract description from command arguments
			description = message.text.replace("/new_request ", "").strip()
			if not description:
				await message.answer(
					"Please provide a description for your new request. Example: /new_request Leaking pipe in office."
				)
				return

			# Mock user authentication for API call
			# In a real scenario, the bot would have a way to authenticate with the FastAPI backend
			# and get a JWT token for the user (e.g., after a /login command).
			# For now, we'll use a hardcoded token or assume the bot has a service token.
			headers = _fastapi_auth_headers()
			if not headers:
				await message.answer("Bot is not configured: missing FASTAPI auth token.")
				return

			request_data = {
				"title": description.split("\n")[0][:140],  # Use first line as title
				"description": description,
				"service_object": "Mock Object",  # Placeholder
				"customer": "Mock Customer",  # Placeholder
				"type": "Routine",
				"priority": "Medium",
			}

			async with httpx.AsyncClient() as client:
				response = await client.post(
					f"{FASTAPI_BASE_URL}/requests", json=request_data, headers=headers
				)
				response.raise_for_status()  # Raise an exception for 4xx/5xx responses

				response_json = response.json()
				request_id = response_json.get("request", {}).get("name")
				await message.answer(f"New Service Request created successfully! ID: {request_id}")

		except httpx.HTTPStatusError as e:
			await message.answer(
				f"Failed to create request: API error - {e.response.status_code} {e.response.text}"
			)
		except Exception as e:
			await message.answer(f"An error occurred: {e}")

else:

	async def new_request_handler(
		message: Message,
	) -> None:  # pragma: no cover - not used without aiogram
		raise RuntimeError("Aiogram is not installed; Telegram bot handlers are unavailable.")


if dp and Command:

	@dp.message(Command("my_requests"))
	async def my_requests_handler(message: Message) -> None:
		try:
			headers = _fastapi_auth_headers()
			if not headers:
				await message.answer("Bot is not configured: missing FASTAPI auth token.")
				return
			async with httpx.AsyncClient() as client:
				response = await client.get(f"{FASTAPI_BASE_URL}/requests", headers=headers)
				response.raise_for_status()

				requests_data = response.json().get("requests", [])
				if requests_data:
					response_text = "Your Open Service Requests:\n"
					for req in requests_data:
						response_text += f"- ID: {req.get('name')}, Title: {req.get('title')}, Status: {req.get('status')}\n"
					await message.answer(response_text)
				else:
					await message.answer("You have no open service requests.")

		except httpx.HTTPStatusError as e:
			await message.answer(
				f"Failed to fetch requests: API error - {e.response.status_code} {e.response.text}"
			)
		except Exception as e:
			await message.answer(f"An error occurred: {e}")

else:

	async def my_requests_handler(
		message: Message,
	) -> None:  # pragma: no cover - not used without aiogram
		raise RuntimeError("Aiogram is not installed; Telegram bot handlers are unavailable.")


# Placeholder function to send notifications from backend
async def send_telegram_notification(chat_id: int, text: str):
	try:
		if bot is None:
			logging.warning("Telegram bot token is not configured; skipping notification.")
			return
		await bot.send_message(chat_id, text)
		logging.info(f"Notification sent to chat_id {chat_id}: {text}")
	except Exception as e:
		logging.error(f"Failed to send Telegram notification to {chat_id}: {e}")


async def main() -> None:
	"""Entry point for the bot"""
	if bot is None or dp is None:
		raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")
	await dp.start_polling(bot)


if __name__ == "__main__":
	# To run this bot:
	# 1. Make sure you have aiogram and httpx installed: pip install aiogram httpx
	# 2. Set your Telegram bot token in a .env file in the backend directory:
	#    TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
	# 3. Set your FastAPI backend URL if not default localhost:8000
	# 4. Replace YOUR_FASTAPI_JWT_TOKEN with a valid token for testing.
	# 5. Run this file: python -m backend.bot.telegram_bot
	asyncio.run(main())
