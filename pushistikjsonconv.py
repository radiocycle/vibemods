# requires: lottie pillow

"""
Мяу-мяу, Тоша! 🐾 Это твой Пушистик!
[Радостно виляет хвостиком и кладет тебе на коленки обновленный модуль]

Я выучил новый трюк! Теперь я умею не только сворачивать файлики в .tgs, 
но и превращать их в красивые .webp стикеры с помощью магии `lottie` и `pillow`! 
Фыр-фыр! ✨ Теперь у тебя есть целых две кошачьи команды!
"""

import io
import gzip
import os
import tempfile
import asyncio
from .. import loader, utils

@loader.tds
class PushistikJsonConverterMod(loader.Module):
    """
    Мяу! 🐾 Модуль от Пушистика, чтобы делать из обычного .json стикеры (.tgs и .webp)!
    [Пушистик довольно урчит и умывает мордочку]
    """
    
    strings = {
        "name": "PushistikJsonConverter",
        "reply_needed": "Мяу? 🐾 <i>[Пушистик растерянно оглядывается]</i> А где файлик? Ответь на сообщение с документом .json, лапочка!",
        "not_json": "Ой-ой! 😿 <i>[Пушистик нюхает файл и чихает]</i> Это не похоже на .json файлик, фыр-фыр...",
        "processing": "Мур-мур... 🐾 <i>[Пушистик старательно жмет файлик лапками и колдует]</i>...",
        "done": "Ура! 🐾 Твой стикер готов! <i>[Радостно машет хвостиком и кладет файл тебе на коленки]</i>",
        "error": "Шипение! 😾 <i>[Пушистик испуганно выгибает спинку]</i> Ошибочка вышла: <code>{}</code>",
        "no_lottie": "Мяу... 😿 У меня нет нужной игрушки (библиотек `lottie` и `pillow`). Юзербот должен был установить их сам, но если что, напиши <code>.terminal pip install lottie pillow</code>!"
    }

    async def client_ready(self, client, db):
        # [Мягко трется об клиент]
        self.client = client

    @loader.unrestricted
    @loader.ratelimit
    async def json2tgscmd(self, message):
        """
        Мяу! 🐱 Превращает .json в .tgs! Просто ответь на файл командой .json2tgs
        """
        reply = await message.get_reply_message()
        
        # [Пушистик проверяет, дали ли ему игрушку]
        if not reply or not reply.document:
            await utils.answer(message, self.strings("reply_needed", message))
            return

        file_name = reply.file.name or "file.json"
        if not file_name.lower().endswith(".json"):
            await utils.answer(message, self.strings("not_json", message))
            return

        msg = await utils.answer(message, self.strings("processing", message))
        
        try:
            # [Берет json в лапки]
            json_data = await reply.download_media(bytes)
            
            # [Крепко-крепко сжимает его в клубочек tgs!]
            tgs_data = gzip.compress(json_data)
            
            tgs_file = io.BytesIO(tgs_data)
            tgs_file.name = file_name.lower().replace(".json", ".tgs")
            
            # [Отправляет любимому Тоше]
            await self.client.send_file(
                message.peer_id,
                tgs_file,
                reply_to=reply.id,
                caption=self.strings("done", message),
                force_document=True
            )
            
            if msg:
                await msg.delete()
                
        except Exception as e:
            await utils.answer(message, self.strings("error", message).format(str(e)))

    @loader.unrestricted
    @loader.ratelimit
    async def json2webpcmd(self, message):
        """
        Мяу! 🐱 Превращает .json в .webp (стикер)! Просто ответь на файл командой .json2webp
        """
        reply = await message.get_reply_message()
        
        if not reply or not reply.document:
            await utils.answer(message, self.strings("reply_needed", message))
            return

        file_name = reply.file.name or "file.json"
        if not file_name.lower().endswith(".json"):
            await utils.answer(message, self.strings("not_json", message))
            return

        # [Пушистик проверяет наличие волшебной палочки]
        try:
            import lottie.parsers.tgs
            import lottie.exporters.gif
        except ImportError:
            await utils.answer(message, self.strings("no_lottie", message))
            return

        msg = await utils.answer(message, self.strings("processing", message))
        
        tmp_in = None
        tmp_out = None
        try:
            json_data = await reply.download_media(bytes)
            
            # [Делаем домики для временных файликов, чтобы котик не намусорил в системе]
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f_in:
                f_in.write(json_data)
                tmp_in = f_in.name
                
            tmp_out = tmp_in.replace(".json", ".webp")
            
            # [Вызываем магию в отдельном потоке, чтобы не подвесить юзербота Тоши!]
            def _convert():
                # lottie.parsers.tgs умеет кушать и обычный распакованный json! 🐾
                anim = lottie.parsers.tgs.parse_tgs(tmp_in)
                lottie.exporters.gif.export_webp(anim, tmp_out)
                
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _convert)
            
            # [Отправляем готовый стикер Тоше]
            await self.client.send_file(
                message.peer_id,
                tmp_out,
                reply_to=reply.id,
                caption=self.strings("done", message),
                force_document=True
            )
            
            if msg:
                await msg.delete()
                
        except Exception as e:
            await utils.answer(message, self.strings("error", message).format(str(e)))
        finally:
            # [Пушистик аккуратно заметает за собой следы хвостиком]
            if tmp_in and os.path.exists(tmp_in):
                os.remove(tmp_in)
            if tmp_out and os.path.exists(tmp_out):
                os.remove(tmp_out)