__version__ = (1, 0, 1)
# meta developer: @arachnophiliac

import logging
import aiohttp

from .. import loader, utils
from herokutl.types import Message
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest

logger = logging.getLogger(__name__)


@loader.tds
class ProfileManagerMod(loader.Module):
    """Управление профилем: получение информации и редактирование"""

    strings = {
        "name": "ProfileManager",
        "user_not_found": "❌ <b>Error:</b> User not found.",
        "api_error": "❌ <b>Error:</b> Could not process the request.",
        "info_text": "👤 <b>Profile Info:</b>\n\n<b>Name:</b> {name}\n<b>ID:</b> <code>{id}</code>\n<b>Username:</b> {username}\n<b>Bio:</b> {bio}",
        "no_name_args": "❌ <b>Error:</b> Specify first name.",
        "name_updated": "✅ <b>Name updated successfully.</b>",
        "bio_updated": "✅ <b>Bio updated successfully.</b>",
        "no_ava_source": "❌ <b>Error:</b> Reply to a photo or provide an image link.",
        "ava_updated": "✅ <b>Avatar updated successfully.</b>",
        "download_error": "❌ <b>Error:</b> Failed to download the image from the link."
    }

    strings_ru = {
        "user_not_found": "❌ <b>Ошибка:</b> Пользователь не найден.",
        "api_error": "❌ <b>Ошибка:</b> Не удалось выполнить запрос.",
        "info_text": "👤 <b>Информация о профиле:</b>\n\n<b>Имя:</b> {name}\n<b>ID:</b> <code>{id}</code>\n<b>Юзернейм:</b> {username}\n<b>О себе:</b> {bio}",
        "no_name_args": "❌ <b>Ошибка:</b> Укажи имя (и опционально фамилию).",
        "name_updated": "✅ <b>Имя успешно обновлено.</b>",
        "bio_updated": "✅ <b>Информация «О себе» успешно обновлена.</b>",
        "no_ava_source": "❌ <b>Ошибка:</b> Сделай реплай на фото или укажи ссылку на изображение.",
        "ava_updated": "✅ <b>Аватарка успешно обновлена.</b>",
        "download_error": "❌ <b>Ошибка:</b> Не удалось скачать изображение по ссылке."
    }

    @loader.command(ru_doc="<user|reply> — получить информацию о профиле")
    async def pinfocmd(self, message: Message):
        """<user|reply> — get profile info"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        if args:
            try:
                user = await self._client.get_entity(args)
            except (ValueError, TypeError) as e:
                logger.debug("Entity not found: %s", e)
                return await utils.answer(message, self.strings("user_not_found"))
        elif reply:
            user = await reply.get_sender()
        else:
            user = await self._client.get_me()

        try:
            full_user_req = await self._client(GetFullUserRequest(user))
            full_user = full_user_req.full_user
        except Exception as e:
            logger.exception(e)
            return await utils.answer(message, self.strings("api_error"))

        name = utils.escape_html(user.first_name)
        if user.last_name:
            name += f" {utils.escape_html(user.last_name)}"

        username = f"@{user.username}" if user.username else "<i>None</i>"
        bio = utils.escape_html(full_user.about) if full_user.about else "<i>None</i>"

        text = self.strings("info_text").format(
            name=name,
            id=user.id,
            username=username,
            bio=bio
        )
        await utils.answer(message, text)

    @loader.command(ru_doc="<имя> [фамилия] — изменить своё имя")
    async def setnamecmd(self, message: Message):
        """<first_name> [last_name] — set your name"""
        args = utils.get_args(message)
        if not args:
            return await utils.answer(message, self.strings("no_name_args"))

        first_name = args[0]
        last_name = args[1] if len(args) > 1 else ""

        try:
            await self._client(UpdateProfileRequest(
                first_name=first_name,
                last_name=last_name
            ))
            await utils.answer(message, self.strings("name_updated"))
        except Exception as e:
            logger.exception(e)
            await utils.answer(message, self.strings("api_error"))

    @loader.command(ru_doc="[текст] — изменить информацию «О себе» (пустой аргумент для удаления)")
    async def setbiocmd(self, message: Message):
        """[text] — set your bio (empty to clear)"""
        args = utils.get_args_raw(message)

        try:
            await self._client(UpdateProfileRequest(about=args))
            await utils.answer(message, self.strings("bio_updated"))
        except Exception as e:
            logger.exception(e)
            await utils.answer(message, self.strings("api_error"))

    @loader.command(ru_doc="<ссылка> или реплай — установить аватарку")
    async def setavacmd(self, message: Message):
        """<link|reply> — set your avatar"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        photo_bytes = b""

        if reply and reply.media:
            try:
                photo_bytes = await self._client.download_media(reply, bytes)
            except Exception as e:
                logger.exception(e)
                return await utils.answer(message, self.strings("api_error"))
        elif args:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(args) as resp:
                        resp.raise_for_status()
                        photo_bytes = await resp.read()
            except aiohttp.ClientError as e:
                logger.exception(e)
                return await utils.answer(message, self.strings("download_error"))
        else:
            return await utils.answer(message, self.strings("no_ava_source"))

        try:
            uploaded_file = await self._client.upload_file(photo_bytes)
            await self._client(UploadProfilePhotoRequest(file=uploaded_file))
            await utils.answer(message, self.strings("ava_updated"))
        except Exception as e:
            logger.exception(e)
            await utils.answer(message, self.strings("api_error"))