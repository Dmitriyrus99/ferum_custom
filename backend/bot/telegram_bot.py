import asyncio
import logging
import httpx
import json

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command

from ..config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Base URL for your FastAPI backend
FASTAPI_BASE_URL = "http://localhost:8000/api/v1" # Adjust if your FastAPI is on a different host/port

@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    """This handler receives messages with the `/start` command"""
    await message.answer(f"Hello, {message.from_user.full_name}! I am your Ferum Customizations bot.")

@dp.message(Command("new_request"))
async def new_request_handler(message: types.Message) -> None:
    # This is a simplified example. In a real bot, you'd use FSM (Finite State Machine)
    # to guide the user through providing request details.
    try:
        # Extract description from command arguments
        description = message.text.replace("/new_request ", "").strip()
        if not description:
            await message.answer("Please provide a description for your new request. Example: /new_request Leaking pipe in office.")
            return

        # Mock user authentication for API call
        # In a real scenario, the bot would have a way to authenticate with the FastAPI backend
        # and get a JWT token for the user (e.g., after a /login command).
        # For now, we'll use a hardcoded token or assume the bot has a service token.
        headers = {"Authorization": "Bearer YOUR_FASTAPI_JWT_TOKEN"} # REPLACE WITH ACTUAL TOKEN

        request_data = {
            "title": description.split('\n')[0][:140], # Use first line as title
            "description": description,
            "service_object": "Mock Object", # Placeholder
            "customer": "Mock Customer", # Placeholder
            "type": "Routine",
            "priority": "Medium"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{FASTAPI_BASE_URL}/requests", json=request_data, headers=headers)
            response.raise_for_status() # Raise an exception for 4xx/5xx responses
            
            response_json = response.json()
            request_id = response_json.get("request", {}).get("name")
            await message.answer(f"New Service Request created successfully! ID: {request_id}")

    except httpx.HTTPStatusError as e:
        await message.answer(f"Failed to create request: API error - {e.response.status_code} {e.response.text}")
    except Exception as e:
        await message.answer(f"An error occurred: {e}")

@dp.message(Command("my_requests"))
async def my_requests_handler(message: types.Message) -> None:
    try:
        headers = {"Authorization": "Bearer YOUR_FASTAPI_JWT_TOKEN"} # REPLACE WITH ACTUAL TOKEN
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
        await message.answer(f"Failed to fetch requests: API error - {e.response.status_code} {e.response.text}")
    except Exception as e:
        await message.answer(f"An error occurred: {e}")

# Placeholder function to send notifications from backend
async def send_telegram_notification(chat_id: int, text: str):
    try:
        await bot.send_message(chat_id, text)
        logging.info(f"Notification sent to chat_id {chat_id}: {text}")
    except Exception as e:
        logging.error(f"Failed to send Telegram notification to {chat_id}: {e}")

async def main() -> None:
    """Entry point for the bot"""
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