from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from data.config import ADMIN_LINK, ADMINS, HELP_URL

from utils.db.db_context import DbContext


async def get_inline_keyboard(buttons_data):
    buttons = []

    for button_info in buttons_data["buttons_info"]:
        text_key = button_info.get("text_key")
        callback_data = button_info.get("callback_data")
        url = button_info.get("url")

        if not text_key:
            raise ValueError("Missing 'text_key' in button_info")
        if url or callback_data:
            button_row = []
            if url:
                button_row.append(InlineKeyboardButton(text=f"🌐 {text_key}", url=url))
            if callback_data:
                button_row.append(
                    InlineKeyboardButton(text=f"{text_key}", callback_data=callback_data))
            buttons.append(button_row)

    if not buttons:
        raise ValueError("No valid buttons provided")

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


async def get_admin(telegram_id):
    buttons_data = {
        "telegram_id": telegram_id,
        "buttons_info": [
            {"text_key": 'Управление доступом', "callback_data": "adm_gen"},
            {"text_key": 'Рассылка по пользователям', "callback_data": "adm_newsletter"},
            {"text_key": 'Назад', "callback_data": "menu_start"},
        ]
    }
    return await get_inline_keyboard(buttons_data)


async def get_gen(telegram_id):
    buttons_data = {
        "telegram_id": telegram_id,
        "buttons_info": [
            {"text_key": 'Сгенерировать ключ доступа', "callback_data": "gen_new"},
            {"text_key": 'Список доступных ключей', "callback_data": "gen_list"},
            {"text_key": 'Назад', "callback_data": "menu_admin"},
        ]
    }
    return await get_inline_keyboard(buttons_data)


async def get_main(telegram_id):
    buttons_info = [
        {"text_key": 'Меню', "callback_data": "menu_main"},
        {"text_key": 'Админ-панель', "callback_data": "menu_admin", "condition": str(telegram_id) in ADMINS},
        {"text_key": 'Настройки', "callback_data": "menu_profile"},
    ]

    buttons_info = [info for info in buttons_info if "condition" not in info or info["condition"]]

    buttons_data = {
        "telegram_id": telegram_id,
        "buttons_info": buttons_info
    }

    return await get_inline_keyboard(buttons_data)


async def get_help(telegram_id):
    buttons_data = {
        "telegram_id": telegram_id,
        "buttons_info": [
            {"text_key": 'Инструкция', "url": HELP_URL},
            {"text_key": 'Написать администратору', "url": ADMIN_LINK},
            {"text_key": 'Назад', "callback_data": 'menu_main'},
        ]
    }
    return await get_inline_keyboard(buttons_data)


async def get_profile(telegram_id):
    buttons_data = {
        "telegram_id": telegram_id,
        "buttons_info": [
            {"text_key": 'Управление аккаунтами', "callback_data": "menu_accs"},
            {"text_key": 'Другие настройки', "callback_data": "menu_settings"},
            {"text_key": 'Назад', "callback_data": "menu_start"},
        ]
    }
    return await get_inline_keyboard(buttons_data)


async def get_settings(telegram_id):
    buttons_data = {
        "telegram_id": telegram_id,
        "buttons_info": [
            {"text_key": 'Настройки прокси', "callback_data": "menu_proxy"},
            {"text_key": 'Указать название устройства', "callback_data": "proxy_device"},
            {"text_key": 'Назад', "callback_data": "menu_profile"},
        ]
    }
    return await get_inline_keyboard(buttons_data)


async def get_menu(context: DbContext, telegram_id):
    task_status = await context.get_task_status(telegram_id)
    buttons_data = {
        "telegram_id": telegram_id,
        "buttons_info": [
            {"text_key": 'Запустить задачу', "callback_data": "task_start"} if not task_status else
            {"text_key": 'Остановить задачу', "callback_data": "menu_switch"},
            {"text_key": 'Инструкция', "callback_data": "menu_help"},
            {"text_key": 'В главное меню', "callback_data": "menu_start"},
        ]
    }
    return await get_inline_keyboard(buttons_data)


async def accs_settings(telegram_id):
    buttons_data = {
        "telegram_id": telegram_id,
        "buttons_info": [
            {"text_key": 'Добавить аккаунт', "callback_data": "menu_addacc"},
            {"text_key": 'Список аккаунтов', "callback_data": "menu_acclist"},
            {"text_key": 'Назад', "callback_data": "menu_profile"},
        ]
    }
    return await get_inline_keyboard(buttons_data)


async def get_proxy_settings(context: DbContext, telegram_id):
    server, port, ptype, login, pwd, ipv6 = await context.get_user_proxy_credentials(telegram_id)

    buttons_data = {
        "telegram_id": telegram_id,
        "buttons_info": [
            {"text_key": 'Изменить адрес прокси' if server else 'Указать адрес прокси',
             "callback_data": 'proxy_server'},
            {"text_key": 'Изменить порт прокси' if port else 'Указать порт прокси',
             "callback_data": 'proxy_port'},
            {"text_key": 'Изменить тип прокси' if ptype else 'Указать тип прокси', "callback_data": 'proxy_type'},
            {"text_key": 'Изменить логин прокси' if login else 'Указать логин прокси',
             "callback_data": 'proxy_login'},
            {"text_key": 'Изменить пароль прокси' if pwd else 'Указать пароль прокси',
             "callback_data": 'proxy_password'},
            {"text_key": 'Выключить поддержку IPv6' if ipv6 else 'Включить поддержку IPv6', "callback_data": 'proxy_ipv6'},
            {"text_key": 'Удалить прокси', "callback_data": 'proxy_clear'},
            {"text_key": 'Назад', "callback_data": 'menu_settings'},
        ]
    }
    return await get_inline_keyboard(buttons_data)
