from hydrogram import Client
from hydrogram.enums import UserStatus, ChatType
from hydrogram.errors import (ChannelsTooMuch, InviteRequestSent, UserAlreadyParticipant, ChannelInvalid,
                              ChannelPrivate,
                              ChatInvalid, InviteHashEmpty, InviteHashExpired, InviteHashInvalid, MsgIdInvalid,
                              PeerIdInvalid, UsersTooMuch,
                              UserChannelsTooMuch, ChannelPublicGroupNa, UserBannedInChannel, UserCreator,
                              UserNotParticipant,
                              AuthKeyUnregistered, UserDeactivated, ChatIdInvalid, Unauthorized, UserPrivacyRestricted,
                              UserIdInvalid, UserNotMutualContact, UserKicked, InputUserDeactivated, UserBlocked,
                              UserBot, ChatWriteForbidden, BotGroupsBlocked, BotsTooMuch, ChatAdminRequired, FloodWait)

from data.config import API_HASH, API_ID, system_version, app_version

JoinChannelUpdates = (ChannelsTooMuch, ChannelInvalid, ChannelPrivate, ChatInvalid, InviteHashEmpty, InviteHashExpired,
                      InviteHashInvalid, InviteRequestSent, MsgIdInvalid, PeerIdInvalid, UsersTooMuch,
                      UserAlreadyParticipant, UserChannelsTooMuch)
LeaveChannelUpdates = (ChannelInvalid, ChannelPrivate, ChannelPublicGroupNa, ChatInvalid, MsgIdInvalid,
                       UserBannedInChannel, UserCreator, UserNotParticipant)

BadUpdates = (AuthKeyUnregistered, UserDeactivated)

InviteUpdates = (BotsTooMuch, BotGroupsBlocked, ChannelInvalid, ChannelPrivate, ChatAdminRequired, ChatInvalid,
                 ChatWriteForbidden, InputUserDeactivated, MsgIdInvalid, UsersTooMuch, UserBannedInChannel,
                 UserBlocked, UserBot, UserChannelsTooMuch, UserIdInvalid, UserKicked, UserNotMutualContact,
                 UserPrivacyRestricted)
clients = {}
total_users = {}


async def create_client(number, telegram_id, context):
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
    except (Unauthorized, UserDeactivated):
        await context.del_account(number)
        return None


async def join_channel(client, chat_id):
    try:
        joined = await client.join_chat(chat_id)
        if joined is True:
            return True
    except JoinChannelUpdates as e:
        return JoinChannelUpdates.index(type(e))
    except BadUpdates:
        return False


async def leave_channel(client, chat_id):
    try:
        leaved = await client.leave_chat(chat_id)
        if leaved is True:
            return True
    except LeaveChannelUpdates as e:
        return LeaveChannelUpdates.index(type(e))
    except BadUpdates:
        return False


async def get_chat_info(client, chat):
    try:
        details = await client.get_chat(chat)
        if details.type == ChatType.GROUP or details.type == ChatType.SUPERGROUP:
            is_chat = True
        else:
            is_chat = False
        members_count = details.chat.members_count
        invite_allowed: bool = details.invite_allowed
        restricted = bool(details.is_restricted)
        chat_id = details.chat.id
        return chat_id, is_chat, restricted, invite_allowed, members_count
    except (ChatIdInvalid, PeerIdInvalid):
        return None, None, None, None, None
    except BadUpdates:
        return False, False, False, False, False


async def add_member_method(client, chat_id, group):
    try:
        added = await client.add_chat_members(group, chat_id)
        if added is True:
            return True
    except InviteUpdates as e:
        return InviteUpdates.index(type(e))
    except BadUpdates:
        return False
    except FloodWait as e:
        return e.value


async def fetch_members(context, client, source, target):
    members_target = [
        member_tg.user.id
        async for member_tg in client.get_chat_members(target)
        if not member_tg.user.is_bot
    ]
    valid_members = []
    async for member in client.get_chat_members(source):
        is_valid_member = (
                not member.user.is_bot
                and member.user.status in [UserStatus.LAST_MONTH, UserStatus.LONG_AGO]
                and not member.user.is_deleted
                and not await context.get_blacklist(member.user.id)
                and member.user.id not in members_target
        )
        if is_valid_member:
            valid_members.append(member)
        return valid_members
