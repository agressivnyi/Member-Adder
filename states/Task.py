from aiogram.fsm.state import StatesGroup, State


class Task(StatesGroup):
    dest = State()
    target = State()
