# meta developer: @videcmods
# meta pic: https://raw.githubusercontent.com/coddrago/assets/refs/heads/main/heroku/heroku_logo.png

import asyncio
import contextlib
import os
import re
import shutil
import tempfile
import typing

from herokutl.tl.types import Message

from .. import loader, utils
from ..inline.types import InlineCall


@loader.tds
class AudioToolsMod(loader.Module):
    """Inline audio editor: volume, speed, pitch and sound tuning via ffmpeg"""

    strings = {
        "name": "AudioTools",
        "no_reply": "<b>Ответь командой на аудио, voice, музыку или аудио-документ.</b>",
        "no_ffmpeg": (
            "<b>ffmpeg не найден.</b>\n"
            "Установи ffmpeg в систему или добавь ffmpeg buildpack на Heroku."
        ),
        "menu": (
            "<b>AudioTools</b>\n\n"
            "Файл найден. Выбери действие и введи значение.\n"
            "Примеры: <code>150</code>, <code>75%</code>, <code>+20</code>, <code>-10</code>."
        ),
        "input_volume": "Громкость в процентах: 100 = без изменений, 150 = громче, 50 = тише",
        "input_tempo": "Скорость/темп в процентах: 100 = норма, 150 = быстрее, 75 = медленнее",
        "input_pitch": "Тон в процентах: 100 = норма, 120 = выше, 80 = ниже",
        "input_bass": "Басы от -100 до 100: -50 = убрать, 50 = усилить",
        "input_treble": "Верхние частоты от -100 до 100: -50 = убрать, 50 = усилить",
        "input_echo": "Эхо от 0 до 100: 0 = почти нет, 100 = сильнее",
        "input_stereo": "Ширина стерео в процентах: 0 = почти моно, 100 = норма, 200 = шире",
        "input_custom": "Введи готовую ffmpeg audio-filter строку, например: volume=1.4,atempo=1.2",
        "processing": "<b>Обрабатываю аудио...</b>",
        "bad_value": "<b>Не понял значение.</b>\nВведи число, например: <code>150</code> или <code>75%</code>.",
        "range_error": "<b>Значение вне диапазона.</b>\nДля этого действия нужно: <code>{}</code>.",
        "download_error": "<b>Не получилось скачать аудио.</b>",
        "ffmpeg_error": "<b>ffmpeg вернул ошибку:</b>\n<code>{}</code>",
        "done": "<b>Готово.</b>\nФайл отправлен ниже.",
        "caption": "AudioTools: {action} ({value})",
    }

    ACTIONS = {
        "volume": {
            "title": "Громкость",
            "input": "input_volume",
            "range": (0, 500),
            "range_text": "0..500%",
            "relative": True,
        },
        "tempo": {
            "title": "Скорость",
            "input": "input_tempo",
            "range": (25, 400),
            "range_text": "25..400%",
            "relative": True,
        },
        "pitch": {
            "title": "Тон",
            "input": "input_pitch",
            "range": (50, 200),
            "range_text": "50..200%",
            "relative": True,
        },
        "bass": {
            "title": "Басы",
            "input": "input_bass",
            "range": (-100, 100),
            "range_text": "-100..100",
            "relative": False,
        },
        "treble": {
            "title": "Верх",
            "input": "input_treble",
            "range": (-100, 100),
            "range_text": "-100..100",
            "relative": False,
        },
        "echo": {
            "title": "Эхо",
            "input": "input_echo",
            "range": (0, 100),
            "range_text": "0..100",
            "relative": False,
        },
        "stereo": {
            "title": "Стерео",
            "input": "input_stereo",
            "range": (0, 200),
            "range_text": "0..200%",
            "relative": True,
        },
    }

    @loader.command(alias="audiofx")
    async def soundcmd(self, message: Message):
        """Ответь на аудио: открыть inline-редактор звука"""

        reply = await message.get_reply_message()
        if not reply or not getattr(reply, "media", None):
            await utils.answer(message, self.strings("no_reply"))
            return

        if not shutil.which("ffmpeg"):
            await utils.answer(message, self.strings("no_ffmpeg"))
            return

        await self.inline.form(
            self.strings("menu"),
            message=message,
            reply_markup=self._markup(reply),
        )

    def _markup(self, reply: Message) -> list:
        return [
            [
                self._input_btn("volume", reply),
                self._input_btn("tempo", reply),
            ],
            [
                self._input_btn("pitch", reply),
                self._input_btn("bass", reply),
            ],
            [
                self._input_btn("treble", reply),
                self._input_btn("echo", reply),
            ],
            [
                self._input_btn("stereo", reply),
                {
                    "text": "Нормализация",
                    "callback": self._preset_handler,
                    "args": (reply, "normalize"),
                },
            ],
            [
                {
                    "text": "Реверс",
                    "callback": self._preset_handler,
                    "args": (reply, "reverse"),
                },
                {
                    "text": "Свой фильтр",
                    "input": self.strings("input_custom"),
                    "handler": self._custom_handler,
                    "args": (reply,),
                },
            ],
            [{"text": "Закрыть", "action": "close"}],
        ]

    def _input_btn(self, action: str, reply: Message) -> dict:
        data = self.ACTIONS[action]
        return {
            "text": data["title"],
            "input": self.strings(data["input"]),
            "handler": self._percent_handler,
            "args": (reply, action),
        }

    async def _percent_handler(self, call: InlineCall, query: str, reply: Message, action: str):
        data = self.ACTIONS[action]
        value = self._parse_number(query, relative=data["relative"])

        if value is None:
            await call.edit(
                self.strings("bad_value"),
                reply_markup={"text": "Назад", "callback": self._back, "args": (reply,)},
            )
            return

        min_value, max_value = data["range"]
        if value < min_value or value > max_value:
            await call.edit(
                self.strings("range_error").format(data["range_text"]),
                reply_markup={"text": "Назад", "callback": self._back, "args": (reply,)},
            )
            return

        audio_filter = self._build_filter(action, value)
        shown_value = f"{value:g}%"
        await self._process(call, reply, audio_filter, data["title"], shown_value)

    async def _custom_handler(self, call: InlineCall, query: str, reply: Message):
        audio_filter = query.strip()
        if not audio_filter:
            await call.edit(
                self.strings("bad_value"),
                reply_markup={"text": "Назад", "callback": self._back, "args": (reply,)},
            )
            return

        await self._process(call, reply, audio_filter, "свой фильтр", audio_filter)

    async def _preset_handler(self, call: InlineCall, reply: Message, preset: str):
        presets = {
            "normalize": ("loudnorm=I=-16:TP=-1.5:LRA=11", "нормализация", "auto"),
            "reverse": ("areverse", "реверс", "auto"),
        }

        audio_filter, title, shown_value = presets[preset]
        await self._process(call, reply, audio_filter, title, shown_value)

    async def _back(self, call: InlineCall, reply: Message):
        await call.edit(self.strings("menu"), reply_markup=self._markup(reply))

    async def _process(
        self,
        call: InlineCall,
        reply: Message,
        audio_filter: str,
        action_title: str,
        shown_value: str,
    ):
        await call.edit(self.strings("processing"))

        temp_dir = tempfile.mkdtemp(prefix="audio_tools_")
        src = os.path.join(temp_dir, "input_audio")
        out = os.path.join(temp_dir, "audio_tools_result.mp3")

        try:
            downloaded = await self.client.download_media(reply, file=src)
            if not downloaded:
                await call.edit(self.strings("download_error"))
                return

            code, stderr = await self._run_ffmpeg(downloaded, out, audio_filter)
            if code != 0 or not os.path.exists(out) or os.path.getsize(out) == 0:
                await call.edit(
                    self.strings("ffmpeg_error").format(utils.escape_html(stderr[-3500:] or "unknown error")),
                    reply_markup={"text": "Назад", "callback": self._back, "args": (reply,)},
                )
                return

            await self.client.send_file(
                reply.peer_id,
                out,
                caption=self.strings("caption").format(
                    action=action_title,
                    value=shown_value,
                ),
                reply_to=reply.id,
                force_document=False,
            )

            await call.edit(
                self.strings("done"),
                reply_markup={"text": "Закрыть", "action": "close"},
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def _run_ffmpeg(self, src: str, out: str, audio_filter: str) -> typing.Tuple[int, str]:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            src,
            "-map",
            "0:a:0",
            "-vn",
            "-filter:a",
            audio_filter,
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            out,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await proc.communicate()
        return proc.returncode, stderr.decode("utf-8", "ignore").strip()

    def _build_filter(self, action: str, value: float) -> str:
        factor = value / 100

        if action == "volume":
            return f"volume={factor:.6f}"

        if action == "tempo":
            return ",".join(self._atempo_chain(factor))

        if action == "pitch":
            pitch_factor = max(0.5, min(2.0, factor))
            keep_duration = 1 / pitch_factor
            return ",".join(
                [
                    "aresample=44100",
                    f"asetrate={44100 * pitch_factor:.3f}",
                    "aresample=44100",
                    *self._atempo_chain(keep_duration),
                ]
            )

        if action == "bass":
            gain = value / 100 * 20
            return f"bass=g={gain:.3f}"

        if action == "treble":
            gain = value / 100 * 20
            return f"treble=g={gain:.3f}"

        if action == "echo":
            decay = 0.05 + value / 100 * 0.75
            return f"aecho=0.8:0.88:60|180:{decay / 2:.3f}|{decay:.3f}"

        if action == "stereo":
            return f"stereotools=slev={factor:.6f}"

        return "anull"

    def _atempo_chain(self, factor: float) -> list:
        factor = max(0.25, min(4.0, factor))
        chain = []

        while factor < 0.5:
            chain.append("atempo=0.5")
            factor /= 0.5

        while factor > 2.0:
            chain.append("atempo=2.0")
            factor /= 2.0

        chain.append(f"atempo={factor:.6f}")
        return chain

    def _parse_number(self, raw: str, *, relative: bool) -> typing.Optional[float]:
        value = raw.strip().replace(",", ".")
        value = re.sub(r"\s+", "", value)
        value = value.removesuffix("%")

        if not value:
            return None

        try:
            if relative and value[0] in "+-":
                return 100 + float(value)

            return float(value)
        except ValueError:
            return None