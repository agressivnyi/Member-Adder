from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


async def get_proxy_type_kb():
    cancel = 'Назад'
    scheme = ['mtproto', 'https', 'socks5', 'sosks4']

    keyboard = [
        [InlineKeyboardButton(text=key, callback_data=f"ptype_{key}") for key in scheme],
        [InlineKeyboardButton(text=cancel, callback_data='menu_proxy')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
