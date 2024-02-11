import asyncio

from aiogram import Router, types, F
from aiogram.client.session.middlewares.request_logging import logger
from aiogram.enums.parse_mode import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

from data.config import ADMINS, ADMIN_LINK
from keyboards.inline.buttons import get_main
from loader import bot
from states.Auth import SessionCreation
from utils.db.db_context import DbContext

router = Router()


async def check_accounts(context: DbContext):
    while True:
        accounts = await context.get_all_accounts()
        for account in accounts:
            check = await context.get_account(account)
            if check.status == 'bad':
                await context.check_restriction_time(account)
        await asyncio.sleep(600)


async def start_checking(context: DbContext):
    task = asyncio.create_task(check_accounts(context))


@router.message(CommandStart())
async def do_start(message: types.Message, state: FSMContext, context: DbContext):
    telegram_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username
    user = None
    try:
        user = await context.get_or_create_user(telegram_id=telegram_id, full_name=full_name, username=username)
    except Exception as error:
        logger.info(error)
    await state.clear()
    await bot.delete_message(telegram_id, message.message_id)
    mes = await bot.send_message(telegram_id, '...', reply_markup=ReplyKeyboardRemove())
    await bot.delete_message(telegram_id, mes.message_id)
    if user:
        if await context.user_has_auth_key(telegram_id) or str(telegram_id) in ADMINS:
            msg = await bot.send_message(telegram_id,
                                         f'Здравствуйте, <b>{message.from_user.full_name}!</b>',
                                         parse_mode=ParseMode.HTML,
                                         reply_markup=await get_main(telegram_id))
            await context.update_message_id(msg.message_id, telegram_id)
        else:
            await state.set_state(SessionCreation.ask_access_code)
            msg = await bot.send_message(chat_id=telegram_id,
                                         text=f'Привет, {message.from_user.full_name}!\n'
                                              '‼️Для того чтобы пользоваться функциями бота введите код разрешения:\n\n'
                                              'А чтобы получить код разрешения обратитесь к администратору✍️\n\n'
                                              f'{ADMIN_LINK}\n\n'
                                              'Если вы уже зарегистрированы и хотите восстановить подписку, '
                                              'то введите код, который выдал вам бот:',
                                         parse_mode=ParseMode.HTML)
            await context.update_message_id(msg.message_id, telegram_id)


@router.message(F.text, Command("del"))
async def del_handler(message: types.Message, context: DbContext):
    if message.text:
        try:
            await context.del_account(message.text)
            await bot.delete_message(message.from_user.id, message.message_id)
        except Exception as e:
            print(e)
            await bot.delete_message(message.from_user.id, message.message_id)


@router.message(F.text, Command("check"))
async def del_handler(message: types.Message, context: DbContext):
    m = await message.answer("Начинаю проверку аккаунтов...")
    await start_checking(context)
    await asyncio.sleep(10)
    await bot.delete_message(message.from_user.id, m.message_id)