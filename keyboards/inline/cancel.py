from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


async def cancel_back_kb(string):
    cancel_btn = 'Отменить'
    back_btn = 'Назад'
    button_mapping = {
        'c_adm': 'menu_admin',
        'c_sett': 'menu_settings',
        'c_proxy': 'menu_proxy',
        'c_menu': 'menu_main',
        'c_auth': 'menu_accs',
        'c_clear': 'menu_start',
        'b_adm': 'menu_admin',
        'b_menu': 'menu_main',
        'b_auth': 'menu_accs'
    }

    action = button_mapping.get(string, 'default_action')

    buttons = [[InlineKeyboardButton(text=cancel_btn if 'c_' in string else back_btn, callback_data=action)]]

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard
