from aiogram import Bot
from aiogram.enums.parse_mode import ParseMode

from data.config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
