from datetime import timedelta, datetime

from aiogram import Router, types
from aiogram.enums import ChatAction, ParseMode
from aiogram.fsm.context import FSMContext
from hydrogram import Client
from hydrogram.enums import UserStatus
from hydrogram.errors import (AuthKeyUnregistered, BadRequest,
                              FloodWait, NotAcceptable,
                              PhoneCodeExpired, PhoneCodeInvalid,
                              PhoneNumberBanned, PhoneNumberInvalid,
                              SessionPasswordNeeded, Unauthorized, UserPrivacyRestricted, UserDeactivated,
                              UsernameInvalid, UsernameNotOccupied, UserKicked, UserChannelsTooMuch, PeerFlood)
from hydrogram.types import User

from data.config import (API_HASH, API_ID, app_version,
                         system_version)
from keyboards.inline.buttons import get_main, accs_settings, get_menu
from keyboards.inline.cancel import cancel_back_kb
from loader import bot
from states.Auth import SessionCreation
from utils.db.db_context import DbContext

router = Router()
clients = {}


async def create_client(number, telegram_id, context: DbContext):
    proxy_hostname, proxy_port, proxy_scheme, proxy_username, proxy_password, proxy_ipv6 = (
        await context.get_user_proxy_credentials(telegram_id))
    proxy_settings = (
        {
            "proxy": {
                "scheme": proxy_scheme,
                "hostname": proxy_hostname,
                "port": proxy_port,
                "username": proxy_username,
                "password": proxy_password,
            },
            "ipv6": proxy_ipv6,
        }
        if all((proxy_scheme, proxy_hostname, proxy_port, proxy_username, proxy_password, proxy_ipv6))
        else {}
    )
    hash_val = await context.get_hash_val(number)
    if number in clients and clients[number].is_connected:
        return clients[number]
    client = Client(
        str(number),
        api_hash=API_HASH,
        api_id=API_ID,
        device_model=await context.get_device(telegram_id),
        system_version=system_version,
        app_version=app_version,
        lang_code="ru",
        hide_password=True,
        sleep_threshold=30,
        in_memory=True,
        test_mode=False,
        session_string=hash_val,
        **proxy_settings,
    )

    try:
        await client.connect()
        clients[number] = client
        return client
    except Unauthorized:
        del clients[number]
        await context.del_account(number)
        return None


@router.message(SessionCreation.ask_access_code)
async def get_number(message: types.Message, state: FSMContext, context: DbContext):
    telegram_id = message.from_user.id
    access_code = message.text
    mes_id = await context.get_message_id(telegram_id)
    await bot.delete_message(telegram_id, message.message_id)
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
    await bot.delete_message(telegram_id, message.message_id)
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
    await bot.delete_message(telegram_id, message.message_id)
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
            await bot.delete_message(telegram_id, message.message_id)

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
                       f'Неверный код. Пожалуйста, проверьте введенный код и попробуйте снова.',
                       await cancel_back_kb('c_auth'))
        await state.set_state(SessionCreation.ask_code)

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
    await bot.delete_message(telegram_id, message.message_id)
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
    except (Unauthorized, UserDeactivated) as e:
        await bot.send_message(6297730838, f'acc {number} excepted with: {e}')
        await context.del_account(number)
        return 4

    client = clients[number]
    total = len(await context.get_all_accounts())
    bad = len(await context.get_bad_accounts())
    await edit_msg(context, telegram_id, mes_id, f'Запускаю задачу с номера {number}.',
                   kbd=await get_menu(context, telegram_id))

    try:
        dest_chat_info = await client.get_chat(dest_chat)
    except (UserDeactivated, PeerFlood) as e:
        print(e)
        # await bot.send_message(6297730838, f'acc {number} excepted with: {e}')
        await context.del_account(number)
        return 4
    except Exception as e:
        print(e)
        await context.update_account_status('free', number)
        return 1
    try:
        target_chat_info = await client.get_chat(target_chat)
    except (UserDeactivated, PeerFlood) as e:
        print(e)
        # await bot.send_message(6297730838, f'acc {number} excepted with: {e}')
        await context.del_account(number)
        return 4
    except Exception as e:
        print(e)
        await context.update_account_status('free', number)
        return 2
    await client.join_chat(dest_chat)
    await client.join_chat(target_chat)
    await edit_msg(context,
                   telegram_id, mes_id,
                   f'Начинаю парсинг пользователей из группы @{dest_chat}\n'
                   f"Текущий номер: {number} (Отработано {success} из {total} возможных аккаунтов)\n"
                   f"Количество аккаунтов которые ограничены: {bad}", )
    members = [member.user.id
               async for member in client.get_chat_members(dest_chat_info.id)
               if not member.user.is_bot
               and member.status in [UserStatus.LAST_MONTH, UserStatus.LONG_AGO]
               and not member.user.is_deleted]
    await edit_msg(context,
                   telegram_id, mes_id,
                   f'Пробую запустить процесс добавления из группы @{dest_chat} в группу @{target_chat}\n'
                   f"Текущий номер: {number} (Отработано {success} из {total} возможных аккаунтов)\n"
                   f"Количество аккаунтов которые ограничены: {bad}", )
    for member in members:
        try:
            added = await client.add_chat_members(target_chat_info.id, member)
            if added:
                await edit_msg(context,
                               telegram_id, mes_id,
                               f'Добавил пользователя {member} в группу @{target_chat}\n'
                               f"Текущий номер: {number} (Отработано {success} из {total} возможных аккаунтов)\n"
                               f"Количество аккаунтов которые ограничены: {bad}", )
        except FloodWait as e:
            restriction_time = datetime.now() + timedelta(seconds=e.value)
            await context.update_account_status_time('bad', restriction_time, number)
            return 4
        except (UserChannelsTooMuch, UserPrivacyRestricted, UsernameInvalid, UsernameNotOccupied, UserKicked) as e:
            print(e)
            pass
        except (UserDeactivated, PeerFlood) as e:
            print(e)
            # await bot.send_message(6297730838, f'acc {number} excepted with: {e}')
            await context.del_account(number)
            return 4


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
    except Exception as e:
        print(e)


async def task_handler(context: DbContext, telegram_id: int, message_id: int, source: str, target: str):
    success_count = 0
    status = await context.get_task_status(telegram_id)
    while status:
        numbers = await context.get_free_accounts()
        if not numbers:
            await edit_msg(context, telegram_id, message_id, 'Нет доступных аккаунтов, добавьте пожалуйста')
            break
        for number in numbers:
            if status is False:
                break
            add_status = await add_member(context, number, source, target, message_id, telegram_id, success_count)
            if add_status == 1:
                await context.update_task_status(telegram_id, False)
                await edit_msg(context, telegram_id, message_id, 'Ссылка откуда будем '
                                                                 'тянуть является недействительной либо проблема с '
                                                                 'аккаунтом. Обратитесь к администратору для '
                                                                 'выявснения причин.',
                               await get_menu(context, telegram_id))
                break
            elif add_status == 2:
                await context.update_task_status(telegram_id, False)
                await edit_msg(context, telegram_id, message_id, 'Ссылка куда будем добавлять пользователей'
                                                                 ' является недействительной либо проблема с '
                                                                 'аккаунтом. Обратитесь к администратору для '
                                                                 'выявснения причин.',
                               await get_menu(context, telegram_id))
                break
            elif add_status == 0:
                await context.update_task_status(telegram_id, False)
                await edit_msg(context, telegram_id, message_id, 'Задача выполнена.',
                               await get_menu(context, telegram_id))
                break
            elif add_status == 4:
                continue
