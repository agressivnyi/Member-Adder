from aiogram.fsm.state import StatesGroup, State


class SessionCreation(StatesGroup):
    step = State()
    ask_access_code = State()
    ask_number = State()
    ask_code = State()
    ask_2fa = State()
    send_message = State()