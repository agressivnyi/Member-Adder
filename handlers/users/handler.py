import asyncio
from datetime import timedelta, datetime

from aiogram import Router, types
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from hydrogram.errors import (AuthKeyUnregistered, BadRequest,
                              FloodWait, NotAcceptable,
                              PhoneCodeExpired, PhoneCodeInvalid,
                              PhoneNumberBanned, PhoneNumberInvalid,
                              SessionPasswordNeeded, Unauthorized, UserDeactivated)
from hydrogram.types import User

from handlers.TelegramAPI.methods import fetch_members, create_client, clients, get_chat_info, add_member_method, \
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
    if total_users[telegram_id]:
        total_success = total_users[telegram_id]
    else:
        total_users[telegram_id] = total_users
    success_user = 0
    total = len(await context.get_all_accounts())
    bad = len(await context.get_bad_accounts())
    await edit_msg(context, telegram_id, mes_id, f'Запускаю задачу с номера {number}.',
                   kbd=await get_menu(context, telegram_id))
    await edit_msg(context,
                   telegram_id, mes_id,
                   f'Начинаю парсинг пользователей из группы @{dest_chat}\n'
                   f"Текущий номер: {number}  b(Отработано {success} из {total} возможных аккаунтов)\n"
                   f"Количество аккаунтов которые ограничены: {bad}", )
    s_chat_id, s_is_chat, s_restricted, s_invite_allowed, s_members_count = await get_chat_info(client, dest_chat)
    t_chat_id, t_is_chat, t_restricted, t_invite_allowed, t_members_count = await get_chat_info(client, target_chat)
    joined = join_channel(client, t_chat_id)
    if joined is False:
        await context.del_account(number)
        return 7
    if not s_is_chat and not t_is_chat:
        return 6
    if not s_restricted:
        await edit_msg(context,
                       telegram_id, mes_id,
                       f'Начинаю парсинг пользователей из группы @{dest_chat} (ID: {s_chat_id})\n'
                       f"Текущий номер: {number} (Отработано {success} из {total} возможных аккаунтов)\n"
                       f"Количество аккаунтов которые ограничены: {bad}", )

        if s_members_count >= 1000:
            members = await fetch_members(context, client, dest_chat, target_chat)
        else:
            members = []
        if members:
            await edit_msg(context,
                           telegram_id, mes_id,
                           f'<b>Текущий номер:</b> <a href="https://t.me/{number}">{number}</a>\n'
                           f'Спарсил из группы @{dest_chat} {len(members)} участников из {s_members_count} '
                           f'возможных')
            await asyncio.sleep(2)
            await edit_msg(context,
                           telegram_id, mes_id,
                           f'<b>Текущий номер:</b> <a href="https://t.me/{number}">{number}</a>\n'
                           f'В группе @{target_chat} {t_members_count} участников в данный момент')
            if t_invite_allowed:
                for member in members:
                    await asyncio.sleep(5)
                    added = await add_member_method(client, s_chat_id, member)
                    if added is False:
                        await context.del_account(number)
                        return 7
                    if added is True:
                        total_success += 1
                        success_user += 1
                        await edit_msg(context,
                                       telegram_id, mes_id,
                                       f'<b>Текущий номер:</b> <a href="https://t.me/{number}">{number}</a>\n'
                                       f'Добавил пользователя (ID: {member} в группу @{target_chat} из группы '
                                       f'@{dest_chat}\n'
                                       f'Добавлено в текущем аккаунте {success_user} пользователей. '
                                       f'(Общее {total_success})'
                                       f'Всего аккаунтов использовано {success} из {total} возможных({bad} ограничены)')
                    elif added == (0, 1, 7, 9, 13, 14, 15, 16, 17):
                        pass
                    elif added == (2, 3, 4, 5, 6, 11):
                        await context.update_account_status('free', number)
                        return 6
                    elif added == 10:
                        await context.update_account_status('spam', number)
                        return 7
                    elif added >= 1000:
                        restriction_time = datetime.now() + timedelta(seconds=int(added))
                        await context.update_account_status_time('flood', restriction_time, number)
                        return 7
            else:
                await context.update_account_status('free', number)
                return 4
        else:
            await context.update_account_status('free', number)
            return 5

    else:
        await context.update_account_status('free', number)
        return


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
            if status is False:
                break
            add_status = await add_member(context, number, source, target, message_id, telegram_id, success_count)
            success_count += 1
            if add_status == 6:
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
