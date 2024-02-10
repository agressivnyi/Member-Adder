import asyncio
import re

from aiogram import Router, types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from data.config import ADMINS
from filters import IsBotAdminFilter
from handlers.users.pyro_handler import task_handler
from keyboards.inline.buttons import (get_admin, get_gen,
                                      get_help, get_main, get_menu,
                                      get_profile, get_settings, accs_settings, get_proxy_settings)
from keyboards.inline.cancel import cancel_back_kb
from keyboards.inline.pagination import get_proxy_type_kb
from loader import bot
from states import AdminState
from states.Auth import SessionCreation
from states.Task import Task
from states.proxy import Proxy
from utils.db.db_context import DbContext

router = Router()


@router.callback_query(lambda c: c.data.startswith('gen_'))
async def select_lang(callback_query: types.CallbackQuery, context: DbContext):
    telegram_id = callback_query.from_user.id
    await context.update_message_id(callback_query.message.message_id, telegram_id)
    gen = str(callback_query.data.split('_')[
                  1]) if '_' in callback_query.data else 0
    if gen == 'new':
        generated_code = await context.add_auth_key()
        message = (f'<b>Ключ сгенерирован:</b>\n<code>{generated_code}</code>\n<i>'
                   f'Перешлите данное сообщение пользователю которому хотите дать доступ к боту!</i>')
        await bot.edit_message_text(
            text=message,
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=await get_gen(telegram_id),
            parse_mode=ParseMode.HTML
        )
    if gen == 'list':
        keys = await context.get_free_auth_keys()
        key_list = 'Список доступных ключей:'
        key_list += "\n".join([f'\n<code>{key}</code>\n' for key in keys]) if keys else \
            f"Пока вы не сгенерировали ключи..."
        message = f'{key_list}\n'
        try:
            await bot.edit_message_text(
                text=message,
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                reply_markup=await get_gen(telegram_id),
                parse_mode=ParseMode.HTML)
        except TelegramBadRequest:
            await bot.answer_callback_query(callback_query.id, 'Не надо так часто нажимать на кнопки!\n'
                                                               'Результат запроса остается такой же как сейчас.',
                                            show_alert=True)


@router.callback_query(lambda c: c.data.startswith('menu_'))
async def menu_handler(callback_query: types.CallbackQuery, state: FSMContext, context: DbContext):
    telegram_id = callback_query.from_user.id
    await context.update_message_id(callback_query.message.message_id, telegram_id)

    async def edit_message(kbd, msg=None):
        if msg is None:
            msg = "выберите действие:"
        try:
            await bot.edit_message_text(
                text=msg,
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                reply_markup=kbd,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(e)
            await bot.answer_callback_query(callback_query.id, 'Не надо так часто нажимать на кнопки!\n'
                                                               'Результат запроса остается такой же как сейчас.',
                                            show_alert=True)

    menu = str(callback_query.data.split('_')[
                   1]) if '_' in callback_query.data else 0
    session = await context.get_free_accounts()
    if menu == 'main':
        if session:
            await edit_message(await get_menu(context, telegram_id))
        else:
            await edit_message(
                await get_main(telegram_id),
                'Пожалуйста добавьте аккаунты!')
    elif menu == 'help':
        if session:
            await edit_message(await get_help(telegram_id),
                               "<b>📘 Инструкции по использованию бота доступны в нашем канале.</b>\n<i>"
                               "Вы можете ознакомиться с ними, нажав на кнопку ниже, "
                               "где представлена видеоинструкция для вашего удобства."
                               "\n\n⚠️ В случае возникновения вопросов, вы также можете обратиться к администратору, "
                               "нажав на соответствующую кнопку:</i>")
        else:
            await edit_message(
                await accs_settings(telegram_id),
                f'<b>Пожалуйста добавьте аккаунты</b>')
    elif menu == 'start':
        await edit_message(await get_main(telegram_id))
    elif menu == 'profile':
        await edit_message(await get_profile(telegram_id))
    elif menu == 'accs':
        await edit_message(await accs_settings(telegram_id))
    elif menu == 'admin':
        await edit_message(await get_admin(telegram_id))
    elif menu == 'proxy':
        await edit_message(await get_proxy_settings(context, telegram_id))
    elif menu == 'switch':
        await context.update_task_status(telegram_id, False)
        await edit_message(await get_menu(context, telegram_id))
    elif menu == 'addacc':
        await state.clear()
        await edit_message(await cancel_back_kb('c_auth'),
                           '<b>Введите номер телефона в Telegram:</b>')
        await state.set_state(SessionCreation.ask_number)
        await context.update_message_id(callback_query.message.message_id, telegram_id)
    elif menu == 'acclist':
        await edit_message(await cancel_back_kb('b_auth'), await context.get_accounts())
    elif menu == 'settings':
        await state.clear()
        await edit_message(await get_settings(telegram_id))


@router.callback_query(lambda c: c.data.startswith('proxy_'))
async def job_handler(callback_query: types.CallbackQuery, state: FSMContext, context: DbContext):
    telegram_id = callback_query.from_user.id
    await context.update_message_id(callback_query.message.message_id, telegram_id)
    server, port, ptype, login, password, ipv6 = await context.get_user_proxy_credentials(telegram_id)
    proxy = str(callback_query.data.split('_')[
                    1]) if '_' in callback_query.data else 0
    if proxy == 'server':
        serv = server
        m = f'<b>Текущий сервер:</b>\n' + serv + '\n\n' if serv else f'Сервер неустановлен'
        await bot.edit_message_text(text=f"{m}\n<b>Введите новый адрес:</b>",
                                    chat_id=telegram_id,
                                    message_id=callback_query.message.message_id,
                                    reply_markup=await cancel_back_kb('c_proxy'))
        await state.set_state(Proxy.server)
        await state.update_data(tmp_msg_id=callback_query.message.message_id)
    elif proxy == 'type':
        await bot.edit_message_text(
            text=f"<b>Вы выбрали: </b>\n{ptype}\n<b>Выберите новое значение либо отмените действие:</b>",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=await get_proxy_type_kb(),
            parse_mode=ParseMode.HTML
        )
    elif proxy == 'port':
        await bot.edit_message_text(
            text=f"<b>Вы указали порт:</b>\n{port}\n<b>Введите новое значение либо отмените действие:</b>",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=await cancel_back_kb('c_proxy')
        )
        await state.set_state(Proxy.port)
        await state.update_data(tmp_msg_id=callback_query.message.message_id)
    elif proxy == 'login':
        await bot.edit_message_text(
            text=f"<b>Ваш текущий логин:</b>\n{login}\n<b>Введите новое значение либо отмените действие:</b>",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=await cancel_back_kb('c_proxy')
        )
        await state.set_state(Proxy.login)
        await state.update_data(tmp_msg_id=callback_query.message.message_id)
    elif proxy == 'password':
        await bot.edit_message_text(
            text=f"<b>Ваш текущий пароль:</b>\n{password}\n<b>Введите новое значение либо отмените действие:</b>",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=await cancel_back_kb('c_proxy')
        )
        await state.set_state(Proxy.password)
        await state.update_data(tmp_msg_id=callback_query.message.message_id)
    elif proxy == 'ipv6':
        await context.ipv6upd(telegram_id)
        await bot.edit_message_text(
            text=f"Настройки применены",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=await get_proxy_settings(context, telegram_id)
        )
    elif proxy == 'device':
        await bot.edit_message_text(
            text=f"Укажите название устройства: Например Redmi Redmi Note 13",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=await cancel_back_kb('c_sett')

        )
        await state.set_state(Proxy.device)
        await state.update_data(tmp_msg_id=callback_query.message.message_id)
    elif proxy == 'clear':
        await context.clear_proxy(telegram_id)
        await bot.edit_message_text(
            text=f"Данные прокси удалены",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=await get_proxy_settings(context, telegram_id)
        )


@router.callback_query(lambda c: c.data.startswith('adm_'))
async def admin_menu(callback_query: types.CallbackQuery, state: FSMContext, context: DbContext):
    telegram_id = callback_query.from_user.id
    await context.update_message_id(callback_query.message.message_id, telegram_id)
    if str(telegram_id) in ADMINS:
        adm = str(callback_query.data.split('_')[
                      1]) if '_' in callback_query.data else 0
        if adm == 'gen':
            await bot.edit_message_text(
                text='<b>Выберите действие:</b>',
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                reply_markup=await get_gen(telegram_id)
            )
        elif adm == 'newsletter':
            await bot.edit_message_text(
                text="<i>Отправьте текст для рассылки всем пользователям</i>",
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                reply_markup=await cancel_back_kb('c_adm')
            )
            await state.set_state(AdminState.ask_ad_content)
        elif adm == 'back':
            await bot.edit_message_text(
                text='<b>Выберите действие:</b>',
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                reply_markup=await get_main(telegram_id)
            )

    else:
        await bot.edit_message_text(
            text='<b>Выберите действие:</b>',
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=await get_main(telegram_id))


@router.message(AdminState.ask_ad_content, IsBotAdminFilter(ADMINS))
async def send_ad_to_users(message: types.Message, state: FSMContext, context: DbContext):
    users = await context.select_all_users()
    telegram_id = message.from_user.id
    mes_id = await context.get_message_id(telegram_id)
    count = 0
    await bot.edit_message_text(chat_id=telegram_id,
                                text=f'<b>Рассылка запущена</b>',
                                message_id=mes_id,
                                reply_markup=await get_main(telegram_id))
    for user in users:
        user_id = user.telegram_id
        try:
            await message.send_copy(chat_id=user_id)
            count += 1
            await bot.edit_message_text(text=f"<b>Идёт рассылка... Отправлено <u>{count}</u> пользователям</b>",
                                        chat_id=telegram_id,
                                        message_id=mes_id,
                                        reply_markup=await get_main(telegram_id))
            await asyncio.sleep(0.05)
        except Exception as e:
            await bot.edit_message_text(text=f"<b>Рассылка завершилась с ошибкой. Ошибка <u>{e}</u></b>",
                                        chat_id=telegram_id,
                                        message_id=mes_id,
                                        reply_markup=await get_main(telegram_id))
    await bot.edit_message_text(text=f"<b>Рассылка завершена. Отправлено <u>{count}</u> пользователям</b>",
                                chat_id=telegram_id,
                                message_id=mes_id,
                                reply_markup=await get_main(telegram_id))
    await state.clear()


@router.callback_query(lambda c: c.data.startswith('task_'))
async def dest_handler(callback_query: types.CallbackQuery, state: FSMContext, context: DbContext):
    telegram_id = callback_query.from_user.id
    await context.update_message_id(callback_query.message.message_id, telegram_id)
    task = str(callback_query.data.split('_')[
                   1]) if '_' in callback_query.data else 0
    if task == 'start':
        await bot.edit_message_text(text="<b>Введите ссылку либо юзернейм группы откуда будем тянуть пользователей?\n"
                                         "Например:</b> <i>https://t.me/durovchats</i>",
                                    chat_id=telegram_id,
                                    message_id=callback_query.message.message_id,
                                    reply_markup=await cancel_back_kb('c_menu'))
        await state.set_state(Task.dest)


@router.message(Task.dest)
async def dest_handler(message: types.Message, state: FSMContext, context: DbContext):
    telegram_id = message.from_user.id
    mes_id = await context.get_message_id(telegram_id)
    await bot.delete_message(chat_id=telegram_id, message_id=message.message_id)
    match = re.match(r'.*?/([a-zA-Z0-9_\-@]+)$', message.text)
    if match:
        username = match.group(1)
        await state.update_data(from_str=username)
        await bot.edit_message_text(text=f'<b>Введите ссылку либо юзернейм группы куда будем добавлять пользователей?\n'
                                         f'Например:</b> <i>https://t.me/yourgroupusername</i>',
                                    chat_id=telegram_id,
                                    message_id=mes_id,
                                    reply_markup=await cancel_back_kb('c_menu'),
                                    parse_mode=ParseMode.HTML)
        await state.set_state(Task.target)
    else:
        await bot.edit_message_text(text="<b>Некорректно ввели ссылку.\nВведите ссылку либо юзернейм группы откуда "
                                         "будем тянуть пользователей?\n"
                                         "Например:</b> <i>https://t.me/durovchats</i>",
                                    chat_id=telegram_id,
                                    message_id=message.message_id,
                                    reply_markup=await cancel_back_kb('c_menu'))
        await state.set_state(Task.dest)


@router.message(Task.target)
async def target_handler(message: types.Message, state: FSMContext, context: DbContext):
    telegram_id = message.from_user.id
    mes_id = await context.get_message_id(telegram_id)
    await bot.delete_message(chat_id=telegram_id,
                             message_id=message.message_id)
    match = re.match(r'.*?/([a-zA-Z0-9_\-@]+)$', message.text)
    username = match.group(1)
    if match:
        await state.update_data(to_str=username)
        data = await state.get_data()
        fr = data['from_str']
        to = data['to_str']
        await context.update_task_status(telegram_id, True)
        await task_handler(context, telegram_id, mes_id, fr, to)
    else:
        await bot.edit_message_text(
            text="<b>Некорректно ввели ссылку.\nВведите ссылку либо юзернейм группы будем добавлять пользователей?\n"
                 "Например:</b> <i>https://t.me/durovchats</i>",
            chat_id=telegram_id,
            message_id=message.message_id,
            reply_markup=await cancel_back_kb('c_menu'))
        await state.set_state(Task.dest)


@router.callback_query(lambda c: c.data.startswith('ptype_'))
async def type_handler(callback_query: types.CallbackQuery, context: DbContext):
    telegram_id = callback_query.from_user.id
    await context.update_message_id(callback_query.message.message_id, callback_query.from_user.id)
    chosen = str(callback_query.data.split('_')[1])
    await context.set_proxy_type(telegram_id, chosen)
    await bot.edit_message_text(
        text=f"<b>Вы установили тип прокси:</b>{chosen}",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=await get_proxy_type_kb(),
        parse_mode=ParseMode.HTML
    )


@router.message(Proxy.port)
async def port_handler(message: types.Message, state: FSMContext, context: DbContext):
    telegram_id = message.from_user.id
    ud = await state.get_data()
    msg_id = ud['tmp_msg_id']
    await bot.delete_message(telegram_id, message.message_id)
    await context.set_proxy_port(telegram_id, message.text)
    await bot.edit_message_text(text=f'<b>Вы установили порт для прокси:</b>\n\n<pre>{message.text}</pre>',
                                chat_id=telegram_id,
                                reply_markup=await get_proxy_settings(context, telegram_id),
                                message_id=msg_id,
                                parse_mode=ParseMode.HTML)
    await state.clear()


@router.message(Proxy.server)
async def server_handler(message: types.Message, state: FSMContext, context: DbContext):
    telegram_id = message.from_user.id
    ud = await state.get_data()
    msg_id = ud['tmp_msg_id']
    await bot.delete_message(telegram_id, message.message_id)
    await context.set_proxy_server(telegram_id, message.text)
    await bot.edit_message_text(text=f'<b>Вы установили сервер для прокси:</b>\n\n<pre>{message.text}</pre>',
                                chat_id=telegram_id,
                                reply_markup=await get_proxy_settings(context, telegram_id),
                                message_id=msg_id,
                                parse_mode=ParseMode.HTML)
    await state.clear()


@router.message(Proxy.login)
async def login_handler(message: types.Message, state: FSMContext, context: DbContext):
    telegram_id = message.from_user.id
    ud = await state.get_data()
    msg_id = ud['tmp_msg_id']
    await bot.delete_message(telegram_id, message.message_id)
    await context.set_proxy_login(telegram_id, message.text)
    await bot.edit_message_text(text=f'<b>Вы установили логин для прокси:</b>\n\n<pre>{message.text}</pre>',
                                chat_id=telegram_id,
                                reply_markup=await get_proxy_settings(context, telegram_id),
                                message_id=msg_id,
                                parse_mode=ParseMode.HTML)
    await state.clear()


@router.message(Proxy.password)
async def password_handler(message: types.Message, state: FSMContext, context: DbContext):
    telegram_id = message.from_user.id
    ud = await state.get_data()
    msg_id = ud['tmp_msg_id']
    await bot.delete_message(telegram_id, message.message_id)
    await context.set_proxy_password(telegram_id, message.text)
    await bot.edit_message_text(text=f'<b>Вы установили пароль для прокси:</b>\n\n<pre>{message.text}</pre>',
                                chat_id=telegram_id,
                                reply_markup=await get_proxy_settings(context, telegram_id),
                                message_id=msg_id,
                                parse_mode=ParseMode.HTML)
    await state.clear()


@router.message(Proxy.device)
async def device_handler(message: types.Message, state: FSMContext, context: DbContext):
    telegram_id = message.from_user.id
    ud = await state.get_data()
    msg_id = ud['tmp_msg_id']
    await bot.delete_message(telegram_id, message.message_id)
    await context.set_device(telegram_id, message.text)
    await bot.edit_message_text(text=f'<b>Ваше устройство называется:</b>\n\n<pre>{message.text}</pre>',
                                chat_id=telegram_id,
                                reply_markup=await get_proxy_settings(context, telegram_id),
                                message_id=msg_id,
                                parse_mode=ParseMode.HTML)
    await state.clear()
