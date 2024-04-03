import asyncio

from aiogram import Router, types
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from pyrogram.enums import UserStatus
from pyrogram.errors import (AuthKeyUnregistered, BadRequest,
                              FloodWait, NotAcceptable,
                              PhoneCodeExpired, PhoneCodeInvalid,
                              PhoneNumberBanned, PhoneNumberInvalid,
                              SessionPasswordNeeded, Unauthorized, UserDeactivated)
from pyrogram.types import User

from handlers.TelegramAPI.methods import create_client, clients, get_chat_info, add_member_method, \
    total_users, join_channel
from keyboards.inline.buttons import get_main, accs_settings, get_menu
from keyboards.inline.cancel import cancel_back_kb
from loader import bot
from states.Auth import SessionCreation
from utils.db.db_context import DbContext

router = Router()


async def edit_msg(context: DbContext, chat_id, message_id, msg, kbd=None, callback_data=None):
    if kbd is not None:
        reply_markup = kbd
    else:
        reply_markup = await get_menu(context, chat_id)

    if not await context.get_message_id(chat_id):
        await context.update_message_id(callback_data, chat_id)
    try:
        await bot.edit_message_text(
            text=msg,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    except TelegramBadRequest:
        await bot.send_message(chat_id, msg, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


@router.message(SessionCreation.ask_access_code)
async def get_number(message: types.Message, state: FSMContext, context: DbContext):
    telegram_id = message.from_user.id
    access_code = message.text
    mes_id = await context.get_message_id(telegram_id)
    try:
        await bot.delete_message(chat_id=telegram_id, message_id=message.message_id)
    except TelegramBadRequest:
        pass
    if await context.activate_auth_key(access_code, telegram_id):
        success_message = (
            "Код активации успешно принят!\n\n"
            "Выберите действие:"
        )
        await edit_msg(context, telegram_id, mes_id, success_message, await get_main(telegram_id))
        await state.set_state(SessionCreation.ask_number)
    else:
        invalid_code_message = (
            "Введённый вами код неверный.\n\n"
            "Введите другой код"
        )
        await edit_msg(context, telegram_id, mes_id, invalid_code_message, await cancel_back_kb('clear'))
        await state.set_state(SessionCreation.ask_access_code)


@router.message(SessionCreation.ask_number)
async def get_number(message: types.Message, state: FSMContext, context: DbContext):
    telegram_id = message.from_user.id
    mes_id = await context.get_message_id(telegram_id)
    number = message.text
    try:
        await bot.delete_message(chat_id=telegram_id, message_id=message.message_id)
    except TelegramBadRequest:
        pass
    await bot.send_chat_action(telegram_id, ChatAction.TYPING)
    client = await create_client(number, telegram_id, context)
    try:
        sent_code = await client.send_code(number)
        await state.update_data(client_id=telegram_id)
        await state.update_data(client=client)
        await state.update_data(code_hash=sent_code.phone_code_hash)
        await state.update_data(phone=number)
        enter_code_string = "Введите код подтверждения, который вы получили в Telegram.\n\n" \
                            "Если SMS долго не приходит, вы можете запросить повторную отправку кода."
        await edit_msg(context, telegram_id,
                       mes_id,
                       enter_code_string,
                       await cancel_back_kb('c_clear'))
        await state.set_state(SessionCreation.ask_code)

    except FloodWait:
        await edit_msg(context,
                       telegram_id,
                       mes_id,
                       "Слишком много запросов. Пожалуйста, подождите некоторое время и попробуйте снова.",
                       await cancel_back_kb('c_clear')
                       )
        await client.disconnect()
        await state.clear()

    except PhoneNumberInvalid:
        await edit_msg(context,
                       telegram_id,
                       mes_id,
                       "Введённый вами номер телефона некорректен. Пожалуйста, проверьте номер и попробуйте снова.",
                       await cancel_back_kb('c_auth')
                       )
        await client.disconnect()
        await state.clear()

    except PhoneNumberBanned:
        await edit_msg(context,
                       telegram_id,
                       mes_id,
                       "Ваш номер телефона заблокирован. Пожалуйста, свяжитесь с поддержкой.",
                       await cancel_back_kb('c_auth')
                       )
        await client.disconnect()
        await state.clear()

    except NotAcceptable:
        await edit_msg(context,
                       telegram_id,
                       mes_id,
                       "Ваш номер телефона не принят. Пожалуйста, используйте другой номер.",
                       await cancel_back_kb('c_auth')
                       )
        await client.disconnect()
        await state.clear()


@router.message(SessionCreation.ask_code)
async def get_code(message: types.Message, state: FSMContext, context: DbContext):
    await bot.send_chat_action(message.from_user.id, ChatAction.TYPING)
    code = message.text
    telegram_id = message.from_user.id
    try:
        await bot.delete_message(chat_id=telegram_id, message_id=message.message_id)
    except TelegramBadRequest:
        pass
    user_data = await state.get_data()
    client = user_data['client']
    number = user_data['phone']
    mes_id = await context.get_message_id(telegram_id)
    try:
        signed_in = await client.sign_in(phone_number=user_data['phone'],
                                         phone_code_hash=user_data['code_hash'],
                                         phone_code=code)
        if isinstance(signed_in, User):
            session = await client.export_session_string()
            await context.add_accounts(number=number, hash_value=session)
            await state.clear()
            await edit_msg(context, telegram_id,
                           mes_id,
                           f'Аккаунт успешно добавлен в бот ',
                           await accs_settings(telegram_id))
            try:
                await bot.delete_message(chat_id=telegram_id, message_id=message.message_id)
            except TelegramBadRequest:
                pass

    except FloodWait:
        await edit_msg(context, telegram_id,
                       mes_id,
                       "Слишком много запросов. Пожалуйста, подождите некоторое время и попробуйте снова.",
                       await accs_settings(telegram_id))
        await client.disconnect()
        await state.clear()

    except AuthKeyUnregistered:
        await edit_msg(context, telegram_id,
                       mes_id,
                       f'Ваш ключ аутентификации не зарегистрирован. '
                       f'Пожалуйста, выполните процесс авторизации заново.',
                       await accs_settings(telegram_id))
        await client.disconnect()
        await state.clear()

    except PhoneCodeInvalid:
        await edit_msg(context, telegram_id,
                       mes_id,
                       f'Неверный код. Пожалуйста, авторизуйтесь заново, введя код через - к примеру 1-2345.',
                       await accs_settings(telegram_id))
        await state.clear()

    except SessionPasswordNeeded:
        await edit_msg(context, telegram_id,
                       mes_id,
                       f'Требуется ввод пароля двухфакторной аутентификации. Пожалуйста, введите пароль.',
                       await cancel_back_kb('c_auth'))
        await state.set_state(SessionCreation.ask_2fa)

    except PhoneCodeExpired:
        await edit_msg(context, telegram_id,
                       mes_id,
                       f'Время действия кода истекло. Пожалуйста, запросите новый код.',
                       await accs_settings(telegram_id))
        await client.disconnect()
        await state.clear()


@router.message(SessionCreation.ask_2fa)
async def get_2fa(message: types.Message, state: FSMContext, context: DbContext):
    telegram_id = message.from_user.id
    await bot.send_chat_action(message.from_user.id, ChatAction.TYPING)
    try:
        await bot.delete_message(chat_id=telegram_id, message_id=message.message_id)
    except TelegramBadRequest:
        pass
    user_data = await state.get_data()
    client = user_data['client']
    number = user_data['phone']
    mes_id = await context.get_message_id(telegram_id)
    try:
        await client.connect()
    except ConnectionError:
        pass
    try:
        await client.check_password(message.text)
        await edit_msg(context, telegram_id,
                       mes_id,
                       'Аккаунт успешно добавлен в бот.',
                       await accs_settings(telegram_id))
        session = await client.export_session_string()
        await context.add_accounts(number=number, hash_value=session)
    except AuthKeyUnregistered:
        await edit_msg(context, telegram_id,
                       mes_id,
                       f"Ваш ключ аутентификации не зарегистрирован. "
                       f"Пожалуйста, выполните процесс авторизации заново.",
                       await accs_settings(telegram_id))
        await client.disconnect()
        await state.clear()
    except BadRequest:
        await edit_msg(context, telegram_id,
                       mes_id,
                       f"Неверный запрос. "
                       f"Пожалуйста, проверьте введенные данные и попробуйте снова.",
                       await cancel_back_kb('c_auth'))
        return
    await client.disconnect()
    await state.clear()


async def add_member(context: DbContext, number, dest_chat, target_chat, mes_id, telegram_id, success):
    try:
        if number not in clients or not clients[number]:
            clients[number] = await create_client(number, telegram_id, context)
    except (Unauthorized, UserDeactivated):
        await context.del_account(number)
        return 7

    client = clients[number]
    success_user = 0
    total = len(await context.get_all_accounts())
    bad = len(await context.get_bad_accounts())
    status = await context.get_task_status(telegram_id)
    await edit_msg(context, telegram_id, mes_id, f'Запускаю задачу с номера {number}.',
                   kbd=await get_menu(context, telegram_id))
    s_chat_id, s_is_chat, s_restricted, s_invite_allowed, s_members_count = await get_chat_info(client, dest_chat)
    t_chat_id, t_is_chat, t_restricted, t_invite_allowed, t_members_count = await get_chat_info(client, target_chat)
    joined = await join_channel(client, t_chat_id)
    if joined is False:
        await context.del_account(number)
        return 7
    if s_is_chat is False and t_is_chat is False:
        return 6
    if s_restricted is True:
        await context.update_account_status('free', number)
        return 6
    if status is False:
        return False
    await edit_msg(context,
                   telegram_id, mes_id,
                   f'<b>Статус:</b>\n'
                   f'<b>Текущий номер:</b> <a href="https://t.me/{number}">{number}</a>\n\n'
                   f'<b>Начинаю парсинг пользователей с группы </b> @{dest_chat}\n'
                   f'<b>Добавлено в текущем аккаунте:</b> <u>{success_user}</u> пользователей.\n'
                   f'<b>Всего добавлено в группу </b> <u>{total_users[telegram_id]}</u> пользователей.'
                   f'\n'
                   f'<b>Всего аккаунтов использовано:</b> <u>{success}</u> из <u>{total}</u> возможных'
                   f'\n'
                   f'<b>Ограничено (Находятся в флуде):</b> {bad}')

    members_target = [
        member_tg.user.id
        async for member_tg in client.get_chat_members(target_chat)
        if not member_tg.user.is_bot
    ]
    members = [
        member
        async for member in client.get_chat_members(dest_chat)
        if not member.user.is_bot and member.user.status in [UserStatus.LAST_MONTH, UserStatus.LONG_AGO]
           and not member.user.is_deleted and not await context.get_blacklist(member.user.id)
           and member.user.id not in members_target]
    if members:
        await edit_msg(context,
                       telegram_id, mes_id,
                       f'<b>Статус:</b>\n'
                       f'<b>Текущий номер:</b> <a href="https://t.me/{number}">{number}</a>\n\n'
                       '<b>Инфо:</b>\n'
                       f'<b>Целевая группа:</b>\n'
                       f'<b>USERNAME:</b> <a href="https://t.me/{dest_chat}">{dest_chat}</a>\n'
                       f'<b>ID группы:</b> {s_chat_id}\n'
                       f'<b>Количество участников:</b> {s_members_count} (<u>спарсено: {len(members)}</u>)'
                       '\n\n'
                       f'<b>Конечная группа:</b>\n'
                       f'<b>USERNAME:</b> <a href="https://t.me/{target_chat}">{target_chat}</a>\n'
                       f'<b>ID группы:</b> {t_chat_id}\n'
                       f'<b>Количество участников:</b> {t_members_count+total_users[telegram_id]}\n')
        if t_invite_allowed is True:
            for member in members:
                if status is False:
                    return False
                await asyncio.sleep(5)
                added = await add_member_method(context, client, number, member.user.id, t_chat_id)
                if added is False:
                    await context.del_account(number)
                    return 7
                if added is True:
                    total_users[telegram_id] += 1
                    success_user += 1
                    await edit_msg(context,
                                   telegram_id, mes_id,
                                   f'Успешно добавлен пользователь:\n'
                                   f'ФИО: {member.user.full_name}\n'
                                   f'ID: {member.user.id}\n'
                                   f'USERNAME: @{member.user.username}\n'
                                   f'\n'
                                   f'Откуда: @{target_chat}\n'
                                   f'Куда: @{dest_chat}\n\n'
                                   f'<b>Статус:</b>\n'
                                   f'<b>Текущий номер:</b> <a href="https://t.me/{number}">{number}</a>\n'
                                   f'<b>Добавлено в текущем аккаунте:</b> <u>{success_user}</u> пользователей.\n'
                                   f'<b>Всего добавлено в группу </b> <u>{total_users[telegram_id]}</u> пользователей.'
                                   f'\n'
                                   f'<b>Всего аккаунтов использовано:</b> <u>{success}</u> из <u>{total}</u> возможных'
                                   f'\n'
                                   f'<b>Ограничено (Находятся в флуде):</b> {bad}')
                elif (added == 0 or added == 1 or added == 7 or added == 9 or added == 13 or added == 14 or added == 15
                      or added == 16 or added == 17):
                    pass
                elif added == 2 or added == 3 or added == 4 or added == 5 or added == 6 or added == 11:
                    await context.update_account_status('free', number)
                    return 6
                elif added is False:
                    return 7
        else:
            await context.update_account_status('free', number)
            return 4
    else:
        await context.update_account_status('free', number)
        return 5


async def task_handler(context: DbContext, telegram_id: int, message_id: int, source: str, target: str):
    success_count = 0
    status = await context.get_task_status(telegram_id)
    while status:
        numbers = await context.get_free_accounts()
        if not numbers:
            await context.update_task_status(telegram_id, False)
            await edit_msg(context, telegram_id, message_id, 'Нет доступных аккаунтов, добавьте пожалуйста')
            break
        for number in numbers:
            if telegram_id not in total_users:
                total_users[telegram_id] = 0
            if status is False:
                if total_users[telegram_id]:
                    del total_users[telegram_id]
                break
            add_status = await add_member(context, number, source, target, message_id, telegram_id, success_count)
            success_count += 1
            if add_status is False:
                break
            elif add_status == 6:
                await context.update_task_status(telegram_id, False)
                await edit_msg(context, telegram_id, message_id, 'Целевая ссылка/Конечная ссылка не являются группой',
                               await get_menu(context, telegram_id))
                break
            elif add_status == 5:
                await context.update_task_status(telegram_id, False)
                await edit_msg(context, telegram_id, message_id, 'У целевой ссылки нет участников либо они скрыты '
                                                                 'либо недостаточно количество.',
                               await get_menu(context, telegram_id))
                break
            if add_status == 4:
                await context.update_task_status(telegram_id, False)
                await edit_msg(context, telegram_id, message_id, 'У конечной ссылки нет прав на '
                                                                 'добавление пользователей...',
                               await get_menu(context, telegram_id))
                break
            elif add_status == 7:
                continue
