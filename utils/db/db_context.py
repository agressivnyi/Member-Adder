import secrets
import string
from datetime import datetime

from aiogram.client.session.middlewares.request_logging import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from utils.db.models import AuthKey, User, Accounts, Blacklist


def generate_key():
    alphabet = string.ascii_letters + string.digits
    key = '-'.join(
        ''.join(
            secrets.choice(alphabet) for _ in range(4)
        ) for _ in range(3)
    )
    return key


class DbContext:
    def __init__(self):
        self.session: AsyncSession | None = None

    async def get_free_auth_keys(self):
        statement = select(AuthKey.key).filter_by(user_id=None)
        free_keys = await self.session.scalars(statement)
        return [key for key in free_keys.all()]

    async def get_or_create_user(self, full_name, username, telegram_id):
        statement = select(User).filter_by(telegram_id=telegram_id)
        result = await self.session.scalars(statement)
        user = result.first()

        if not user:
            user = User(
                full_name=full_name,
                username=username,
                telegram_id=telegram_id
            )
            self.session.add(user)
            try:
                await self.session.commit()
            except Exception as e:
                logger.exception(e)

        return user

    async def get_user_by_tg_id(self, telegram_id: int):
        statement = select(User).filter_by(telegram_id=telegram_id)
        result = await self.session.scalars(statement)
        return result.first()

    async def select_all_users(self):
        statement = select(User)
        result = await self.session.scalars(statement)
        return result.all()

    async def select_user(self, **kwargs):
        statement = select(User).filter_by(**kwargs)
        result = await self.session.scalars(statement)
        return result.first()

    async def count_users(self):
        statement = select(func.count()).select_from(User)
        count = await self.session.scalar(statement)
        return count

    async def update_user_username(self, username, telegram_id):
        user = await self.get_user_by_tg_id(telegram_id)

        if user:
            user.username = username
            try:
                await self.session.commit()
            except Exception as e:
                logger.exception(e)

    # session

    async def get_free_accounts(self):
        statement = select(Accounts.number).filter_by(status='free')
        accounts = await self.session.scalars(statement)
        return [key for key in accounts.all()]

    async def get_bad_accounts(self):
        statement = select(Accounts.hash_value).filter_by(status='flood')
        accounts = await self.session.scalars(statement)
        return [key for key in accounts.all()]

    async def get_all_accounts(self):
        statement = select(Accounts.number)
        accounts = await self.session.scalars(statement)
        return [key for key in accounts.all()]

    async def get_accounts(self):
        statement = select(Accounts.number, Accounts.status, Accounts.restriction_time)
        accounts = await self.session.execute(statement)
        result = "Список:\n"

        for account in accounts:
            number, status, restriction_time = account
            formatted_time = restriction_time.strftime('%Y-%m-%d %H:%M:%S') if restriction_time else ""
            if status == 'free':
                status = 'не используется (свободен)'
            elif status == 'active':
                status = 'используется'
            elif status == 'flood':
                await self.check_restriction_time(account)
                status = 'ограничен'
            elif status == 'spam':
                await self.check_restriction_time(account)
                status = 'в спаме'
            result += f"<b>{number}</b>  <i>{status}</i> {formatted_time}\n"
        if len(result) == len("<b>Список</b>\n\n"):
            return "<b>Вы ещё не добавили</b>"
        else:
            return result

    async def add_accounts(self, number, hash_value):
        if await self.session_exists(number):
            return False
        else:
            query = Accounts(hash_value=hash_value, number=number)
            self.session.add(query)
            try:
                await self.session.commit()
            except Exception as e:
                logger.exception(e)
                return False
            return True

    async def add_blacklist(self, telegram_id: int):
        if await self.blacklist_exists(telegram_id):
            return False
        else:
            query = Blacklist(telegram_id=telegram_id)
            self.session.add(query)
            try:
                await self.session.commit()
            except Exception as e:
                logger.exception(e)
                return False
            return True

    async def del_account(self, number):
        account = await self.get_account(number)
        if account:
            await self.session.delete(account)
            try:
                await self.session.commit()
                return True
            except Exception as e:
                logger.exception(e)
                return False
        else:
            return False

    async def get_account(self, number: str):
        statement = select(Accounts).filter_by(number=number)
        result = await self.session.scalars(statement)
        return result.first()

    async def get_blacklist(self, telegram_id: int):
        statement = select(Blacklist).filter_by(telegram_id=telegram_id)
        result = await self.session.scalars(statement)
        return result.first()

    async def get_status(self, number):
        account = await self.get_account(number)
        status = account.status
        if status == 'active':
            return 'active'
        elif status == 'flood':
            if await self.check_restriction_time(number):
                return 'flood'
        else:
            return 'free'

    async def get_task_status(self, telegram_id):
        user = await self.get_user_by_tg_id(telegram_id)
        status = user.task_status if user else False
        return status

    async def update_task_status(self, telegram_id, task_status: bool):
        user = await self.get_user_by_tg_id(telegram_id)
        if user:
            user.task_status = task_status
            try:
                await self.session.commit()
                return True
            except Exception as e:
                logger.exception(e)
                return False

    async def update_account_status(self, status, number):
        account = await self.get_account(number)
        if account:
            account.status = status
            try:
                await self.session.commit()
            except Exception as e:
                logger.exception(e)

    async def update_account_status_time(self, status, restriction_time_seconds, number):
        account = await self.get_account(number)

        if account:
            account.status = status
            account.restriction_time = restriction_time_seconds
            try:
                await self.session.commit()
            except Exception as e:
                logger.exception(e)

    async def session_exists(self, number):
        return bool(await self.get_account(number))

    async def blacklist_exists(self, telegram_id: int):
        return bool(await self.get_blacklist(telegram_id))

    async def check_restriction_time(self, number):
        account = await self.get_account(number)
        if account:
            current_time = datetime.now()
            if account.restriction_time and current_time > account.restriction_time:
                account.status = 'free'
                account.restriction_time = None
                try:
                    await self.session.commit()
                    return False
                except Exception as e:
                    logger.exception(e)
                    return True
            else:
                return False
        else:
            return False

    async def update_message_id(self, message_id, telegram_id):
        user = await self.get_user_by_tg_id(telegram_id)

        if user:
            user.last_message_id = message_id
            try:
                await self.session.commit()
            except Exception as e:
                logger.exception(e)

    async def get_message_id(self, telegram_id):
        user = await self.get_user_by_tg_id(telegram_id)
        last_message_id = user.last_message_id if user else False
        return last_message_id

    async def add_auth_key(self):
        key = generate_key()
        auth_key = AuthKey(key=key)
        self.session.add(auth_key)
        try:
            await self.session.commit()
        except Exception as e:
            logger.exception(e)
        return key

    async def activate_auth_key(self, key, telegram_id):
        statement = select(AuthKey).filter_by(key=key, is_active=False)
        result = await self.session.scalars(statement)
        auth_key = result.first()

        if auth_key:
            if auth_key.user_id is None:
                auth_key.user_id = telegram_id
                auth_key.is_active = True
                try:
                    await self.session.commit()
                except Exception as e:
                    logger.exception(e)

                return True

        return False

    async def get_user_auth_key(self, telegram_id):
        user = await self.get_user_by_tg_id(telegram_id)

        if user:
            stmt = select(AuthKey).filter_by(
                user_id=user.telegram_id, is_active=True)
            result = await self.session.scalars(stmt)
            auth_key = result.first()

            if auth_key:
                return auth_key.key

        return None

    async def user_has_auth_key(self, telegram_id):
        return bool(await self.get_user_auth_key(telegram_id))

    async def get_auth_key(self, key):
        stmt = select(AuthKey).filter_by(key=key)
        result = await self.session.scalars(stmt)
        auth_key = result.first()
        return auth_key.key if auth_key else None

    async def key_exists(self, key):
        return bool(await self.get_auth_key(key))

    async def set_device(self, telegram_id, device_name):
        user = await self.get_user_by_tg_id(telegram_id)
        if user:
            user.device_name = device_name
            try:
                await self.session.commit()
            except Exception as e:
                logger.exception(e)

    async def get_device(self, telegram_id):
        user = await self.get_user_by_tg_id(telegram_id)
        device = user.device_name if user else 'Redmi Redmi Note 13 Pro'
        return device

    async def get_hash_val(self, number):
        account = await self.get_account(number)
        device = account.hash_value if account else False
        return device

    # PROXY
    async def get_user_proxy_credentials(self, user_id):
        user = await self.get_user_by_tg_id(user_id)
        if user:
            server = user.proxy_server
            port = user.proxy_port
            ptype = user.proxy_type
            login = user.proxy_login
            pwd = user.proxy_password
            ipv6 = user.proxy_ipv6
            return server, port, ptype, login, pwd, ipv6

        return None, None, None, None, None, False

    async def set_proxy_server(self, telegram_id, server):
        user = await self.get_user_by_tg_id(telegram_id)
        if user:
            user.proxy_server = server
            try:
                await self.session.commit()
            except Exception as e:
                logger.exception(e)

    async def set_proxy_port(self, telegram_id, port):
        user = await self.get_user_by_tg_id(telegram_id)
        if user:
            user.proxy_port = port
            try:
                await self.session.commit()
            except Exception as e:
                logger.exception(e)

    async def set_proxy_type(self, telegram_id, ptype):
        user = await self.get_user_by_tg_id(telegram_id)
        if user:
            user.proxy_type = ptype
            try:
                await self.session.commit()
            except Exception as e:
                logger.exception(e)

    async def set_proxy_login(self, telegram_id, login):
        user = await self.get_user_by_tg_id(telegram_id)
        if user:
            user.proxy_login = login
            try:
                await self.session.commit()
            except Exception as e:
                logger.exception(e)

    async def set_proxy_password(self, telegram_id, password):
        user = await self.get_user_by_tg_id(telegram_id)
        if user:
            user.proxy_password = password
            try:
                await self.session.commit()
            except Exception as e:
                logger.exception(e)

    async def ipv6upd(self, telegram_id):
        user = await self.get_user_by_tg_id(telegram_id)
        if user:
            user.proxy_ipv6 = not user.proxy_ipv6
            try:
                await self.session.commit()
            except Exception as e:
                logger.exception(e)

    async def clear_proxy(self, telegram_id: int):
        user = await self.get_user_by_tg_id(telegram_id)
        if user:
            user.proxy_server = ''
            user.proxy_port = ''
            user.proxy_type = ''
            user.proxy_login = ''
            user.proxy_password = ''
            user.proxy_ipv6 = False
            try:
                await self.session.commit()
                return True
            except Exception as e:
                logger.exception(e)
                return False
        else:
            return False
