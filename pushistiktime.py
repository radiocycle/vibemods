# requires: pytz

"""
Мяу-мяу! 🐾 Приветик, Тоша! 
[Пушистик аккуратно берет клубочек с кодом и перевязывает его ленточкой HTML]

Я всё понял! Злые звездочки и кавычки из Маркдауна больше не будут нам мешать.
Я заменил их на красивые и надежные HTML-теги, как ты и просил! Фыр-фыр! 💖✨
"""

import asyncio
import datetime
import pytz
from telethon.tl.functions.account import UpdateProfileRequest
from .. import loader, utils

@loader.tds
class PushistikTimeMod(loader.Module):
    """
    Мяу! 🐾 Модуль от Пушистика, чтобы смотреть время и вставлять его в ник! 
    [Пушистик радостно виляет хвостиком и готов играть со временем]
    """
    
    strings = {
        "name": "PushistikTime",
        # [Пушистик аккуратно поменял разметку на HTML! 🐾]
        "time_msg": "🐾 Мяу-мяу! В твоем часовом поясе (<code>{tz}</code>) сейчас: <b>{time}</b> 🕰✨\n<i>[Пушистик ласково мурлычет]</i>",
        "invalid_tz": "Ой-ой... 😿 <i>[Пушистик растерянно моргает]</i> Кажется, часовой пояс <code>{tz}</code> неправильный! Напиши циферку (например 3) или название (UTC)!",
        "autotime_on": "Мур-р-р! 🐾 Авто-время в нике включено! Буду обновлять каждую минутку! ✨",
        "autotime_off": "Фыр-фыр! 🛑 Авто-время выключено. Я вернул твой старый ник, лапочка! 🌸",
    }

    def __init__(self):
        # [Пушистик сделал конфиг супер-умным! 🐾]
        self.config = loader.ModuleConfig(
            "TIMEZONE", 
            "UTC",
            "Мур? 🐾 Укажи часовой пояс! Можно текстом ('Europe/Moscow', 'UTC') или циферкой смещения (например: 3 для UTC+3)"
        )
        self.autotime_enabled = False
        self.original_first_name = ""
        self.original_last_name = ""
        self._task = None

    async def client_ready(self, client, db):
        # [Приветственно машет лапкой]
        self.client = client

    def _get_timezone(self):
        """
        [Пушистик нюхает конфиг и превращает его в правильное время! 🐈]
        """
        tz_val = self.config["TIMEZONE"]
        
        # Если Тоша написал циферку (например 3, -5) или строчку с цифрой ("+3") 🐾
        if isinstance(tz_val, int) or (isinstance(tz_val, str) and tz_val.lstrip('+-').isdigit()):
            offset = int(tz_val)
            # Создаем временную зону по смещению
            tz = datetime.timezone(datetime.timedelta(hours=offset))
            tz_name = f"UTC{'+' if offset > 0 else ''}{offset}"
            return tz, tz_name
        
        # Если это текст, например 'Europe/Moscow' или 'UTC'
        tz_name = str(tz_val)
        tz = pytz.timezone(tz_name)
        return tz, tz_name

    @loader.unrestricted
    @loader.ratelimit
    async def timecmd(self, message):
        """
        Мяу! 🐱 Показывает актуальное время! Просто напиши .time
        """
        try:
            # [Ловим время лапками!]
            tz, tz_name = self._get_timezone()
            current_time = datetime.datetime.now(tz).strftime("%H:%M:%S | %d.%m.%Y")
            await utils.answer(
                message, 
                self.strings("time_msg", message).format(tz=tz_name, time=current_time)
            )
        except Exception:
            # [Ушки грустно опускаются]
            await utils.answer(
                message, 
                self.strings("invalid_tz", message).format(tz=str(self.config["TIMEZONE"]))
            )

    @loader.unrestricted
    @loader.ratelimit
    async def autotimecmd(self, message):
        """
        Мур-мяу! 🐾 Включает или выключает время в твоем нике! Пиши .autotime
        """
        if self.autotime_enabled:
            # [Нажимает кнопочку ВЫКЛ]
            self.autotime_enabled = False
            if self._task:
                self._task.cancel()
            
            try:
                await self.client(UpdateProfileRequest(
                    first_name=self.original_first_name,
                    last_name=self.original_last_name
                ))
            except Exception:
                pass
            
            await utils.answer(message, self.strings("autotime_off", message))
        else:
            # [Нажимает кнопочку ВКЛ]
            self.autotime_enabled = True
            
            me = await self.client.get_me()
            self.original_first_name = me.first_name or ""
            
            last_name = me.last_name or ""
            if " | " in last_name:
                self.original_last_name = last_name.split(" | ")[0].strip()
            else:
                self.original_last_name = last_name
            
            self._task = asyncio.create_task(self._time_updater())
            await utils.answer(message, self.strings("autotime_on", message))

    async def _time_updater(self):
        """
        [Крадется каждую минуту ровно в 00 секунд, чтобы обновить ник!] 🐾
        """
        while self.autotime_enabled:
            try:
                # Берем самую свежую настроечку
                tz, _ = self._get_timezone()
                now = datetime.datetime.now(tz)
                
                time_str = now.strftime("%H:%M")
                
                if self.original_last_name:
                    new_last_name = f"{self.original_last_name} | {time_str}"
                else:
                    new_last_name = f"| {time_str}"
                
                await self.client(UpdateProfileRequest(
                    last_name=new_last_name
                ))
                
                # [Котенок спит ровно до следующей минуты 🐈💤]
                sleep_seconds = 60 - datetime.datetime.now().second
                await asyncio.sleep(sleep_seconds)
                
            except Exception:
                # [Если что-то не так — прячемся на 5 секунд]
                await asyncio.sleep(5)