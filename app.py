import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.session.middlewares.request_logging import logger
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from middlewares.context import DbContextMiddleware


def setup_handlers(dispatcher: Dispatcher) -> None:
    from handlers import setup_routers
    dispatcher.include_router(setup_routers())


def setup_middlewares(dispatcher: Dispatcher, bot: Bot) -> None:
    from middlewares.throttling import ThrottlingMiddleware
    dispatcher.message.middleware(ThrottlingMiddleware(slow_mode_delay=0.5))


def setup_filters(dispatcher: Dispatcher) -> None:
    from filters import ChatPrivateFilter
    dispatcher.message.filter(ChatPrivateFilter(chat_type=["private"]))


async def setup_aiogram(dispatcher: Dispatcher, bot: Bot) -> None:
    logger.info("Configuring aiogram")
    setup_handlers(dispatcher=dispatcher)
    setup_middlewares(dispatcher=dispatcher, bot=bot)
    setup_filters(dispatcher=dispatcher)
    logger.info("Configured aiogram")


async def aiogram_on_startup_polling(dispatcher: Dispatcher, bot: Bot) -> None:
    from utils.notify_admins import on_startup_notify

    logger.info("Starting polling")
    await bot.delete_webhook(drop_pending_updates=True)
    await setup_aiogram(bot=bot, dispatcher=dispatcher)
    await on_startup_notify(bot=bot)


async def aiogram_on_shutdown_polling(dispatcher: Dispatcher, bot: Bot):
    logger.info("Stopping polling")
    await bot.session.close()
    await dispatcher.storage.close()


def main():
    """CONFIG"""
    from aiogram.enums import ParseMode
    from middlewares.db import DbSessionMiddleware
    from data.config import base_settings, BOT_TOKEN
    from aiogram.fsm.storage.memory import MemoryStorage

    engine = create_async_engine(url=base_settings, echo=False)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    storage = MemoryStorage()
    dispatcher = Dispatcher(storage=storage)

    logger.info("Database connected")
    dispatcher.update.outer_middleware(DbContextMiddleware())
    dispatcher.update.outer_middleware(DbSessionMiddleware(sessionmaker))

    dispatcher.startup.register(aiogram_on_startup_polling)
    dispatcher.shutdown.register(aiogram_on_shutdown_polling)
    asyncio.run(dispatcher.start_polling(bot, close_bot_session=True))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped!")
