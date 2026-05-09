import asyncio
import psutil
import time
import platform
from .. import loader, utils

@loader.tds
class KittyServerMod(loader.Module):
    """🐾 Модуль от Пушистика для управления сервером, мур-р-р!"""
    strings = {"name": "KittyServer"}

    async def syscmd(self, message):
        """<команда> - 🐾 Выполнить консольную команду (мяу!)"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, "Мяу? 🐾 <i>[Пушистик наклоняет голову]</i> А какую команду выполнить, лапочка?")
        
        await utils.answer(message, "<i>[Пушистик быстро-быстро стучит лапками по клавиатуре...] 🐾✨</i>")
        
        try:
            process = await asyncio.create_subprocess_shell(
                args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            result = (stdout + stderr).decode('utf-8', errors='ignore').strip()
            if not result:
                result = "[Пушистик обнюхал результат, но там пусто! Фыр-фыр 😸]"
            
            out = f"<b>🐾 Команда:</b> <code>{args}</code>\n\n<b>✨ Мур-результат:</b>\n<code>{result[:4000]}</code>"
            await utils.answer(message, out)
        except Exception as e:
            await utils.answer(message, f"Ой-ой! 🙀 <i>[Пушистик испуганно прижал ушки]</i> Ошибочка:\n<code>{e}</code>")

    async def statscmd(self, message):
        """- 🐾 Показать, как чувствует себя сервер (мур!)"""
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        sys_os = platform.system()
        release = platform.release()
        
        text = (
            "<b>📊 Мяу-статистика сервера! <i>[Пушистик гордо показывает график]</i> 🐾</b>\n\n"
            f"💻 <b>Процессор (мозги):</b> {cpu}%\n"
            f"🧠 <b>Оперативка (память котика):</b> {ram.percent}% <i>({ram.used // 1048576}MB / {ram.total // 1048576}MB)</i>\n"
            f"💾 <b>Диск (место для вкусняшек):</b> {disk.percent}% <i>(Свободно: {disk.free // 1073741824}GB)</i>\n"
            f"⚙️ <b>Система:</b> {sys_os} {release}"
        )
        await utils.answer(message, text)

    async def uptimecmd(self, message):
        """- 🐾 Узнать, сколько времени сервер не спит"""
        uptime_seconds = time.time() - psutil.boot_time()
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        
        await utils.answer(message, f"⏱ <b>Сервер мурлычет без сна уже:</b> {hours} ч. {minutes} мин. 🐾\n<i>[Пушистик сладко зевает и потягивается]</i>")
        
    async def rebootcmd(self, message):
        """- 🐾 Осторожно! Перезагрузить сервер (фыр!)"""
        await utils.answer(message, "<i>[Пушистик тянется лапкой к большой красной кнопке...] 🐾 Уходим в перезагрузку! Мяу!</i>")
        try:
            cmd = "sudo reboot" if platform.system() != "Windows" else "shutdown /r /t 0"
            await asyncio.create_subprocess_shell(cmd)
        except Exception as e:
            await utils.answer(message, f"Ой! 😿 Кнопочка не нажалась:\n<code>{e}</code>")