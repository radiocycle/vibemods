# Мяу-мяу! Приветик, мой хороший! 🐾
# [Пушистик радостно виляет хвостиком и приносит тебе этот чудесный модуль в зубках]
# Я буду звать своих пушистых друзей из разных уголков интернета, 
# чтобы они радовали тебя своими милыми мордашками! Мур-р-р~ ✨💖
# Здесь нет никаких сложных ключиков, только свободные и добрые котики!

# meta developer: @kitty_mods
# scope: hikka_min 1.3.0
# scope: hikka_only

import aiohttp
import random
from .. import loader, utils

@loader.tds
class KittyPicsMod(loader.Module):
    """Милый модуль для призыва пушистых друзей (котиков!) 🐾"""
    
    strings = {
        "name": "KittyPics",
        "searching": "🐾 <b>Мяу! [Пушистик зажмуривается и зовет друзей...] Ищу котика!</b>",
        "error": "😿 <b>Ой-ой... Котики куда-то спрятались! [Жалобно пищит] Ошибка:</b> <code>{}</code>"
    }

    async def catcmd(self, message):
        """- Позвать случайного котика (картинка) 🐾"""
        # [Аккуратно нажимает на кнопочку отправки сообщения]
        await utils.answer(message, self.strings("searching"))
        
        # Мисочки с бесплатными котиками без ключей! Фыр-фыр!
        apis = [
            "https://api.thecatapi.com/v1/images/search",
            "https://shibe.online/api/cats?count=1"
        ]
        
        api_url = random.choice(apis)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        # Достаем ссылочку из API лапкой
                        if "thecatapi" in api_url:
                            img_url = data[0]["url"]
                        else:
                            img_url = data[0]
                            
                        # [Мурлычет, отправляя пушистого друга!]
                        await message.client.send_file(
                            message.peer_id,
                            img_url,
                            caption="🐾 <b>Мяу! Смотри, какой пушистик пришел к нам в гости!</b> 💖\n<i>[Радостно трется об экран]</i>",
                            reply_to=message.reply_to_msg_id
                        )
                        await message.delete()
                    else:
                        await utils.answer(message, self.strings("error").format("Мисочка пуста, мур... HTTP " + str(resp.status)))
        except Exception as e:
            # [Испуганно прижимает ушки, если что-то сломалось]
            await utils.answer(message, self.strings("error").format(str(e)))

    async def catvidcmd(self, message):
        """- Позвать игривого котика (гифка/видео) 🐾"""
        await utils.answer(message, self.strings("searching"))
        
        try:
            async with aiohttp.ClientSession() as session:
                # Специальный запросик для гифок!
                async with session.get("https://api.thecatapi.com/v1/images/search?mime_types=gif") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        gif_url = data[0]["url"]
                            
                        # Отправляем видео/гифку
                        await message.client.send_file(
                            message.peer_id,
                            gif_url,
                            caption="🐾 <b>Мяу! Этот котенок очень любит бегать и играть!</b> 💖\n<i>[Прыгает и весело ловит свой хвостик]</i>",
                            reply_to=message.reply_to_msg_id
                        )
                        await message.delete()
                    else:
                        await utils.answer(message, self.strings("error").format("Никто не хочет играть, мур... HTTP " + str(resp.status)))
        except Exception as e:
            await utils.answer(message, self.strings("error").format(str(e)))