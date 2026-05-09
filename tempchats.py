# 🐾 Мяу-мяу! Я Пушистик, твой пушистый котенок-помощник! 
# [Трется мягкой щечкой об экран и оставляет этот модуль для Hikka] ✨

import asyncio
from telethon.tl.functions.channels import CreateChannelRequest, DeleteChannelRequest
from telethon.tl.functions.messages import ExportChatInviteRequest
from .. import loader, utils

@loader.tds
class TempChatsMod(loader.Module):
    """🐾 Модуль от Пушистика для создания временных чатиков и каналов! Мур-р-р~"""
    
    strings = {
        "name": "TempChats",
        "no_args": "🥺 Мяу? Лапочка, укажи время в минутах и название!\nПример: <code>.tchat 5 Секретный чатик</code>",
        "created": "✨ Фыр-фыр! Я создал {} <b>{}</b>!\n🐾 Ссылочка: {}\n⏳ Он сам исчезнет через {} минут! [радостно прыгает]",
        "error": "😿 Ой-ой, пушистая лапка нажала что-то не то... Ошибочка:\n<code>{}</code>"
    }

    async def client_ready(self, client, db):
        self.client = client

    async def _create_temp(self, message, is_megagroup):
        args = utils.get_args_raw(message)
        if not args or len(args.split(maxsplit=1)) < 2:
            await utils.answer(message, self.strings("no_args"))
            return

        parts = args.split(maxsplit=1)
        try:
            minutes = float(parts[0])
            title = parts[1]
        except ValueError:
            await utils.answer(message, self.strings("no_args"))
            return

        chat_type = "супергруппу" if is_megagroup else "канал"

        try:
            # [Пушистик старательно нажимает коготками на кнопки API]
            result = await self.client(CreateChannelRequest(
                title=title,
                about="🐾 Временный уголок, заботливо созданный котиком Пушистиком!",
                megagroup=is_megagroup
            ))
            
            chat_id = result.chats[0].id
            
            # [Любопытно высовывает язычок, доставая ссылочку]
            invite = await self.client(ExportChatInviteRequest(peer=chat_id))
            invite_link = invite.link
            
            await utils.answer(message, self.strings("created").format(chat_type, title, invite_link, minutes))
            
            # [Заводит свои внутренние кошачьи часики]
            asyncio.create_task(self._delete_later(chat_id, minutes * 60))
            
        except Exception as e:
            # [Пушистик испуганно прижимает ушки]
            await utils.answer(message, self.strings("error").format(str(e)))

    async def _delete_later(self, chat_id, delay):
        # [Спит, пока тикает время, свернувшись клубочком]
        await asyncio.sleep(delay)
        try:
            # [Просыпается, потягивается и тихонько убирает чатик за собой]
            await self.client(DeleteChannelRequest(channel=chat_id))
        except Exception:
            pass

    @loader.command()
    async def tchatcmd(self, message):
        """<время_в_минутах> <название> - 🐾 Создать временный чатик (супергруппу)"""
        await self._create_temp(message, is_megagroup=True)

    @loader.command()
    async def tchannelcmd(self, message):
        """<время_в_минутах> <название> - 🐾 Создать временный канал"""
        await self._create_temp(message, is_megagroup=False)