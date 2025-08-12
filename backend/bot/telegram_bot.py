import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart

from ..config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    """This handler receives messages with the `/start` command"""
    await message.answer(f"Hello, {message.from_user.full_name}! I am your Ferum Customizations bot.")

# Placeholder for other command handlers
# @dp.message(Command("new_request"))
# async def new_request_handler(message: types.Message) -> None:
#     await message.answer("Please provide details for your new request.")

# @dp.message(Command("my_requests"))
# async def my_requests_handler(message: types.Message) -> None:
#     await message.answer("Fetching your requests...")

async def main() -> None:
    """Entry point for the bot"""
    await dp.start_polling(bot)

if __name__ == "__main__":
    # To run this bot:
    # 1. Make sure you have aiogram installed: pip install aiogram
    # 2. Set your Telegram bot token in a .env file in the backend directory:
    #    TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
    # 3. Run this file: python -m backend.bot.telegram_bot
    asyncio.run(main())
