from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from utils.db.db_context import DbContext


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: sessionmaker):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        session: AsyncSession
        async with self.session_pool() as session:
            context: DbContext = data["context"]
            context.session = session

            return await handler(event, data)
