import logging

from aiogram import Bot

from data.config import ADMINS, dev


async def on_startup_notify(bot: Bot):
    if dev is True:
        for admin in ADMINS:
            try:
                bot_properties = await bot.me()
                message = ["<b>Бот успешно загрузился.</b>\n",
                           f"<b>Айди бота:</b> {bot_properties.id}",
                           f"<b>Имя пользователя:</b> {bot_properties.username}"]
                await bot.send_message(int(admin), "\n".join(message))
            except Exception as err:
                logging.exception(err)
