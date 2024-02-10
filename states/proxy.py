from aiogram.fsm.state import StatesGroup, State


class Proxy(StatesGroup):
    server = State()
    port = State()
    login = State()
    password = State()
    device = State()
