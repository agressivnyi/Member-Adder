import time

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message, CallbackQuery


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, slow_mode_delay=0.5):
        self.user_timeouts = {}
        self.slow_mode_delay = slow_mode_delay
        super(ThrottlingMiddleware, self).__init__()

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id if isinstance(event, Message) else event.from_user.id
        current_time = time.time()

        last_request_time = self.user_timeouts.get(user_id, 0)
        if current_time - last_request_time < self.slow_mode_delay:
            if isinstance(event, Message):
                await event.reply("Stop flood please")
            elif isinstance(event, CallbackQuery):
                await event.answer("Stop flood please")
            return

        else:
            self.user_timeouts[user_id] = current_time
            return await handler(event, data)

