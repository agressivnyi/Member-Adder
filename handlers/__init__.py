from aiogram import Router

from filters import ChatPrivateFilter


def setup_routers() -> Router:
    from .users import start, callback, handler
    from .errors import error_handler

    router = Router()
    start.router.message.filter(ChatPrivateFilter(chat_type=["private"]))

    router.include_routers(start.router, handler.router, error_handler.router, callback.router)

    return router
