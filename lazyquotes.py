# meta developer: @cachxd
# requires: Pillow aiohttp pilmoji

"""
Цитаты с кастомным фоном (фото/гиф/видео).
Команды: lq, lfq
"""

import asyncio
import base64
import io
import os
import subprocess
import tempfile

import aiohttp
from PIL import Image, ImageDraw, ImageFont

try:
    from pilmoji import Pilmoji
    from pilmoji.source import GoogleEmojiSource
    HAS_PILMOJI = True
except ImportError:
    HAS_PILMOJI = False

from telethon.tl.functions.messages import SaveGifRequest
from telethon.tl.functions.photos import GetUserPhotosRequest
from telethon.tl.types import InputDocument

from .. import loader, utils

QUOTE_W = 960
QUOTE_H = 540

# дефолтные шрифты — скачиваются автоматически если нет в конфиге
DEFAULT_FONT_URL = (
    "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/"
    "NotoSans/NotoSans-Regular.ttf"
)
DEFAULT_EMOJI_FONT_URL = (
    "https://github.com/googlefonts/noto-emoji/raw/main/fonts/NotoColorEmoji.ttf"
)

FONT_PATHS_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]

MIME_MAP = {
    b"\xff\xd8\xff": ("image/jpeg", "photo"),
    b"\x89PNG": ("image/png", "photo"),
    b"GIF8": ("image/gif", "gif"),
    b"RIFF": ("image/webp", "photo"),  # уточняется ниже
    b"\x1aE\xdf\xa3": ("video/webm", "video"),
    b"\x00\x00\x00": ("video/mp4", "video"),  # ftyp box, уточняется
}


def _detect_mime(data: bytes) -> tuple[str, str]:
    """Возвращает (mime, тип: photo/gif/video)."""
    if data[4:8] == b"ftyp" or data[4:8] == b"moov":
        return "video/mp4", "video"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "photo"
    for magic, val in MIME_MAP.items():
        if data[:len(magic)] == magic:
            return val
    return "application/octet-stream", "video"


def _find_font(paths: list[str]) -> str | None:
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def _display_name(user) -> str:
    if not user:
        return "Unknown"
    first = getattr(user, "first_name", "") or ""
    last = getattr(user, "last_name", "") or ""
    name = (first + " " + last).strip()
    return name or getattr(user, "username", None) or str(getattr(user, "id", "Unknown"))


def _circle_mask(size: tuple[int, int]) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size[0] - 1, size[1] - 1), fill=255)
    return mask


def _avatar_circle(data: bytes, diameter: int) -> Image.Image:
    src = Image.open(io.BytesIO(data)).convert("RGBA").resize((diameter, diameter), Image.LANCZOS)
    out = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    out.paste(src, mask=_circle_mask((diameter, diameter)))
    return out


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    result: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            result.append("")
            continue
        cur = ""
        for word in paragraph.split():
            trial = (cur + " " + word).strip()
            if dummy.textbbox((0, 0), trial, font=font)[2] <= max_w:
                cur = trial
            else:
                if cur:
                    result.append(cur)
                cur = word
        if cur:
            result.append(cur)
    return result or [""]


def _draw_text_line(
    image: Image.Image,
    pos: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    emoji_font_path: str | None,
) -> None:
    if HAS_PILMOJI and emoji_font_path:
        with Pilmoji(image, source=GoogleEmojiSource) as p:
            p.text(pos, text, fill, font=font, emoji_scale_factor=1.15)
    else:
        ImageDraw.Draw(image).text(pos, text, font=font, fill=fill)


def _build_overlay(
    size: tuple[int, int],
    text: str,
    author: str,
    avatar_data: bytes | None,
    font_path: str | None = None,
    emoji_font_path: str | None = None,
    timestamp: str | None = None,
) -> Image.Image:
    W, H = size
    pad = max(40, W // 16)
    avatar_d = max(56, H // 8)
    bar_h = avatar_d + 32
    bar_y = H - bar_h

    av_margin = (bar_h - avatar_d) // 2
    av_x = av_margin
    av_y = bar_y + av_margin

    regular = font_path or _find_font(FONT_PATHS_REGULAR)
    sz_text = max(28, H // 14)
    sz_name = max(18, H // 22)
    sz_time = max(14, H // 30)

    font_text = ImageFont.truetype(regular, sz_text) if regular else ImageFont.load_default()
    font_name = ImageFont.truetype(regular, sz_name) if regular else ImageFont.load_default()
    font_time = ImageFont.truetype(regular, sz_time) if regular else ImageFont.load_default()

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 145))
    overlay = Image.alpha_composite(overlay, dark)

    zone_top = pad
    zone_h = H - bar_h - pad * 2
    zone_w = W - pad * 2

    lines = _wrap_text(text, font_text, zone_w)
    line_h = font_text.getbbox("Ag")[3] + 8
    block_h = len(lines) * line_h
    y0 = zone_top + max(0, (zone_h - block_h) // 2)

    shadow_overlay = overlay.copy()
    draw_shadow = ImageDraw.Draw(shadow_overlay)
    for i, line in enumerate(lines):
        lw = draw_shadow.textbbox((0, 0), line, font=font_text)[2]
        x = (W - lw) // 2
        y = y0 + i * line_h
        draw_shadow.text((x + 2, y + 2), line, font=font_text, fill=(0, 0, 0, 150))
    overlay = Image.alpha_composite(overlay, shadow_overlay)

    for i, line in enumerate(lines):
        dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        lw = dummy_draw.textbbox((0, 0), line, font=font_text)[2]
        x = (W - lw) // 2
        y = y0 + i * line_h
        _draw_text_line(overlay, (x, y), line, font_text, (255, 255, 255, 255), emoji_font_path)

    bar = Image.new("RGBA", (W, bar_h), (0, 0, 0, 110))
    overlay.paste(bar, (0, bar_y), bar)
    draw = ImageDraw.Draw(overlay)

    if avatar_data:
        av_img = _avatar_circle(avatar_data, avatar_d)
        overlay.paste(av_img, (av_x, av_y), av_img)
    else:
        draw.ellipse((av_x, av_y, av_x + avatar_d, av_y + avatar_d), fill=(70, 70, 70, 210))
        try:
            draw.text(
                (av_x + avatar_d // 2, av_y + avatar_d // 2),
                (author[0] if author else "?").upper(),
                font=font_name,
                fill=(255, 255, 255),
                anchor="mm",
            )
        except Exception:
            pass

    draw.ellipse(
        (av_x - 2, av_y - 2, av_x + avatar_d + 2, av_y + avatar_d + 2),
        outline=(255, 255, 255, 160),
        width=2,
    )

    # ник + таймтег
    name_x = av_x + avatar_d + 14
    name_center_y = av_y + avatar_d // 2
    name_h = font_name.getbbox("Ag")[3]
    time_h = font_time.getbbox("Ag")[3] if timestamp else 0
    gap = 4
    block_name_h = name_h + (gap + time_h if timestamp else 0)
    name_y = name_center_y - block_name_h // 2

    draw.text((name_x + 1, name_y + 1), f"— {author}", font=font_name, fill=(0, 0, 0, 150))
    draw.text((name_x, name_y), f"— {author}", font=font_name, fill=(255, 255, 255, 255))

    if timestamp:
        time_y = name_y + name_h + gap
        draw.text((name_x + 1, time_y + 1), timestamp, font=font_time, fill=(0, 0, 0, 120))
        draw.text((name_x, time_y), timestamp, font=font_time, fill=(200, 200, 200, 220))

    return overlay


def _crop_16_9(img: Image.Image) -> Image.Image:
    target = 16 / 9
    w, h = img.size
    if w / h > target:
        new_w = int(h * target)
        img = img.crop(((w - new_w) // 2, 0, (w - new_w) // 2 + new_w, h))
    elif w / h < target:
        new_h = int(w / target)
        img = img.crop((0, (h - new_h) // 2, w, (h - new_h) // 2 + new_h))
    return img


def _render_photo(
    bg_bytes: bytes,
    text: str,
    author: str,
    avatar_data: bytes | None,
    font_path: str | None = None,
    emoji_font_path: str | None = None,
    timestamp: str | None = None,
) -> bytes:
    bg = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
    bg = _crop_16_9(bg).resize((QUOTE_W, QUOTE_H), Image.LANCZOS)
    overlay = _build_overlay((QUOTE_W, QUOTE_H), text, author, avatar_data, font_path, emoji_font_path, timestamp)
    result = Image.alpha_composite(bg, overlay).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _render_video(
    bg_bytes: bytes,
    text: str,
    author: str,
    avatar_data: bytes | None,
    src_ext: str,
    font_path: str | None = None,
    emoji_font_path: str | None = None,
    timestamp: str | None = None,
) -> str:
    overlay = _build_overlay((QUOTE_W, QUOTE_H), text, author, avatar_data, font_path, emoji_font_path, timestamp)

    with tempfile.NamedTemporaryFile(suffix=src_ext, delete=False) as f:
        f.write(bg_bytes)
        bg_path = f.name

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        overlay.save(f, format="PNG")
        ov_path = f.name

    out_fd, out_path = tempfile.mkstemp(suffix=".mp4")
    os.close(out_fd)

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", bg_path,
                "-i", ov_path,
                "-filter_complex",
                f"[0:v]crop=min(iw\\,ih*16/9):min(ih\\,iw*9/16),"
                f"scale={QUOTE_W}:{QUOTE_H},setsar=1[bg];"
                "[bg][1:v]overlay=0:0",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", "-an",
                out_path,
            ],
            check=True,
            capture_output=True,
        )
    finally:
        os.unlink(bg_path)
        os.unlink(ov_path)

    return out_path


async def _download_with_mime(url: str) -> tuple[bytes, str, str]:
    """Возвращает (data, mime, kind) где kind: photo/gif/video."""
    async with aiohttp.ClientSession() as s:
        async with s.get(url, timeout=aiohttp.ClientTimeout(total=40)) as r:
            r.raise_for_status()
            content_type = r.headers.get("Content-Type", "").split(";")[0].strip()
            data = await r.read()

    mime, kind = _detect_mime(data)
    # Content-Type приоритетнее магии для видео
    if content_type and content_type != "application/octet-stream":
        mime = content_type
        if "gif" in content_type:
            kind = "gif"
        elif "video" in content_type:
            kind = "video"
        elif "image" in content_type:
            kind = "photo"

    return data, mime, kind


async def _get_avatar(client, user) -> bytes | None:
    try:
        photos = await client(GetUserPhotosRequest(user_id=user.id, offset=0, max_id=0, limit=1))
        if not photos.photos:
            return None
        buf = io.BytesIO()
        await client.download_media(photos.photos[0], buf)
        buf.seek(0)
        return buf.read()
    except Exception:
        return None


async def _unsave_gif(client, sent_message) -> None:
    try:
        doc = sent_message.media.document
        await client(SaveGifRequest(
            id=InputDocument(
                id=doc.id,
                access_hash=doc.access_hash,
                file_reference=doc.file_reference,
            ),
            unsave=True,
        ))
    except Exception:
        pass


def _is_gif_doc(message) -> bool:
    from telethon.tl import types as tl
    try:
        doc = message.media.document
        return any(isinstance(a, tl.DocumentAttributeAnimated) for a in doc.attributes)
    except Exception:
        return False


@loader.tds
class LazyQuotesMod(loader.Module):
    """Цитаты с кастомным фоном (фото/гиф/видео). Команды: .lq, .lfq"""

    strings = {
        "name": "LazyQuotes",
        "no_reply": "❌ <b>Ответь на сообщение с текстом.</b>",
        "no_text": "❌ <b>В сообщении нет текста.</b>",
        "no_bg": "❌ <b>Укажи фон в настройках модуля</b> (.config LazyQuotes)",
        "processing": "⏳ <b>Генерирую цитату...</b>",
        "error": "❌ <b>Ошибка:</b> <code>{}</code>",
        "no_user": "❌ <b>Пользователь не найден.</b>",
        "lfq_usage": (
            "❌ <b>Использование:</b>\n"
            "<code>.lfq @username/id текст</code> — фейковая цитата\n"
            "<code>.lfq текст</code> (ответ) — автор из ответа, текст свой"
        ),
        "label_photo": "Фото",
        "label_gif": "GIF",
        "label_video": "Видео",
        "label_audio": "Аудио",
        "label_sticker": "Стикер",
        "label_file": "Файл",
        "label_geo": "Геолокация",
        "label_contact": "Контакт",
        "_cfg_bg_url": "Прямая ссылка на фон цитаты (фото, гиф или видео).",
        "_cfg_font_url": (
            "Ссылка на шрифт (.ttf/.otf). "
            f"По умолчанию: {DEFAULT_FONT_URL}"
        ),
        "_cfg_emoji_font_url": (
            "Ссылка на шрифт эмодзи (.ttf). "
            f"По умолчанию: {DEFAULT_EMOJI_FONT_URL}"
        ),
        "_cfg_timezone": "Часовой пояс для таймтега. Пример: -5, 0, +3 (UTC offset).",
    }

    strings_en = {
        "label_photo": "Photo",
        "label_gif": "GIF",
        "label_video": "Video",
        "label_audio": "Audio",
        "label_sticker": "Sticker",
        "label_file": "File",
        "label_geo": "Location",
        "label_contact": "Contact",
        "no_reply": "❌ <b>Reply to a message with text.</b>",
        "no_text": "❌ <b>The message has no text.</b>",
        "no_bg": "❌ <b>Set a background in module config</b> (.config LazyQuotes)",
        "processing": "⏳ <b>Generating quote...</b>",
        "error": "❌ <b>Error:</b> <code>{}</code>",
        "no_user": "❌ <b>User not found.</b>",
        "lfq_usage": (
            "❌ <b>Usage:</b>\n"
            "<code>.lfq @username/id text</code> — fake quote\n"
            "<code>.lfq text</code> (reply) — author from reply, custom text"
        ),
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "bg_url",
                None,
                lambda: self.strings["_cfg_bg_url"],
            ),
            loader.ConfigValue(
                "font_url",
                DEFAULT_FONT_URL,
                lambda: self.strings["_cfg_font_url"],
            ),
            loader.ConfigValue(
                "emoji_font_url",
                DEFAULT_EMOJI_FONT_URL,
                lambda: self.strings["_cfg_emoji_font_url"],
            ),
            loader.ConfigValue(
                "timezone",
                0,
                lambda: self.strings["_cfg_timezone"],
                validator=loader.validators.Integer(minimum=-12, maximum=14),
            ),
        )
        self._font_cache: dict[str, str] = {}

    async def lsetbgcmd(self, message):
        """(reply) — установить фон из файла в ответном сообщении."""
        reply = await message.get_reply_message()
        if not reply or not reply.media:
            return await utils.answer(message, "❌ <b>Ответь на сообщение с медиафайлом.</b>")

        await utils.answer(message, "⏳ <b>Загружаю файл...</b>")
        buf = io.BytesIO()
        await message.client.download_media(reply.media, buf)
        buf.seek(0)
        data = buf.read()

        # определяем расширение
        from telethon.tl import types as tl
        ext = ".jpg"
        if reply.photo:
            ext = ".jpg"
        elif hasattr(reply.media, "document"):
            doc = reply.media.document
            mime = getattr(doc, "mime_type", "") or ""
            ext_map = {
                "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
                "image/webp": ".webp", "video/mp4": ".mp4", "video/webm": ".webm",
            }
            ext = ext_map.get(mime, ".mp4")

        self.db.set("LazyQuotes", "bg_bytes", base64.b64encode(data).decode())
        self.db.set("LazyQuotes", "bg_ext", ext)
        self.config["bg_url"] = "from_file"
        await utils.answer(message, f"✅ <b>Фон установлен из файла</b> (<code>{ext}</code>, {len(data) // 1024} КБ)")

    def _fmt_time(self, dt) -> str | None:
        if not dt:
            return None
        from datetime import timezone, timedelta
        offset = timedelta(hours=int(self.config["timezone"]))
        tz = timezone(offset)
        # Telethon иногда отдаёт naive datetime — принудительно считаем UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz).strftime("%H:%M")

    async def _unsave_reply_gif(self, client, reply) -> None:
        if reply and _is_gif_doc(reply):
            await _unsave_gif(client, reply)

    async def _get_cached_font(self, url: str) -> str | None:
        if not url:
            return None
        if url in self._font_cache and os.path.exists(self._font_cache[url]):
            return self._font_cache[url]
        ext = ".otf" if url.lower().split("?")[0].endswith(".otf") else ".ttf"
        try:
            data = await _download_with_mime(url)
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                f.write(data[0])
                path = f.name
            self._font_cache[url] = path
            return path
        except Exception:
            return None

    def _media_label(self, reply) -> str | None:
        """Возвращает локализованный лейбл медиа или None если текст есть."""
        from telethon.tl import types as tl
        m = reply.media
        if not m:
            return None
        if isinstance(m, tl.MessageMediaDocument):
            doc = m.document
            attrs = {type(a): a for a in doc.attributes}
            if tl.DocumentAttributeAnimated in attrs:
                return f"[{self.strings('label_gif')}]"
            if tl.DocumentAttributeVideo in attrs:
                return f"[{self.strings('label_video')}]"
            if tl.DocumentAttributeAudio in attrs:
                a = attrs[tl.DocumentAttributeAudio]
                return f"[{'Voice' if a.voice else self.strings('label_audio')}]"
            if tl.DocumentAttributeSticker in attrs:
                return f"[{self.strings('label_sticker')}]"
            return f"[{self.strings('label_file')}]"
        if isinstance(m, tl.MessageMediaPhoto):
            return f"[{self.strings('label_photo')}]"
        if isinstance(m, tl.MessageMediaGeo):
            return f"[{self.strings('label_geo')}]"
        if isinstance(m, tl.MessageMediaContact):
            return f"[{self.strings('label_contact')}]"
        return f"[{self.strings('label_file')}]"

    async def lqcmd(self, message):
        """(reply) — создать цитату из ответного сообщения."""
        reply = await message.get_reply_message()
        if not reply:
            return await utils.answer(message, self.strings("no_reply"))
        label = self._media_label(reply)
        raw = reply.raw_text or ""
        text = f"{label} {raw}".strip() if (label and raw) else (raw or label or "")
        if not text:
            return await utils.answer(message, self.strings("no_text"))

        await utils.answer(message, self.strings("processing"))
        sender = await reply.get_sender()
        await self._unsave_reply_gif(message.client, reply)
        ts = self._fmt_time(reply.date)
        await self._send_quote(message, text, _display_name(sender), sender, timestamp=ts)

    async def lfqcmd(self, message):
        """[@user/id текст] или [reply текст] — фейковая цитата с любым автором и текстом."""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        if not args and not reply:
            return await utils.answer(message, self.strings("lfq_usage"))

        target_user = None
        text = ""
        author = "Unknown"

        if args:
            parts = args.split(None, 1)
            first = parts[0]
            is_user_ref = first.startswith("@") or first.lstrip("-").isdigit()

            if is_user_ref:
                if len(parts) < 2:
                    return await utils.answer(message, self.strings("lfq_usage"))
                text = parts[1].strip()
                try:
                    ent = int(first) if first.lstrip("-").isdigit() else first
                    target_user = await message.client.get_entity(ent)
                    author = _display_name(target_user)
                except Exception:
                    return await utils.answer(message, self.strings("no_user"))
            else:
                text = args.strip()
                if not reply:
                    return await utils.answer(message, self.strings("lfq_usage"))
                sender = await reply.get_sender()
                target_user = sender
                author = _display_name(sender)
        else:
            label = self._media_label(reply)
            raw = reply.raw_text or ""
            text = f"{label} {raw}".strip() if (label and raw) else (raw or label or "")
            await self._unsave_reply_gif(message.client, reply)
            if not text:
                return await utils.answer(message, self.strings("no_text"))
            sender = await reply.get_sender()
            target_user = sender
            author = _display_name(sender)

        await utils.answer(message, self.strings("processing"))
        ts = self._fmt_time(reply.date if reply else None)
        await self._send_quote(message, text, author, target_user, timestamp=ts)

    async def _send_quote(self, message, text: str, author: str, user, timestamp: str | None = None):
        bg_url = self.config["bg_url"]
        if not bg_url:
            return await utils.answer(message, self.strings("no_bg"))

        try:
            if bg_url == "from_file":
                raw_b64 = self.db.get("LazyQuotes", "bg_bytes", None)
                if not raw_b64:
                    return await utils.answer(message, self.strings("no_bg"))
                bg_bytes = base64.b64decode(raw_b64)
                ext = self.db.get("LazyQuotes", "bg_ext", ".jpg")
                mime, kind = _detect_mime(bg_bytes)
                # если ext явно видео/гиф — доверяем ему
                if ext in (".gif",):
                    kind = "gif"
                elif ext in (".mp4", ".webm", ".mov", ".avi", ".mkv"):
                    kind = "video"
                font_path, emoji_font_path = await asyncio.gather(
                    self._get_cached_font(self.config["font_url"]),
                    self._get_cached_font(self.config["emoji_font_url"]),
                )
            else:
                (bg_bytes, mime, kind), font_path, emoji_font_path = await asyncio.gather(
                    _download_with_mime(bg_url),
                    self._get_cached_font(self.config["font_url"]),
                    self._get_cached_font(self.config["emoji_font_url"]),
                )

            avatar_data = None
            if user:
                avatar_data = await _get_avatar(message.client, user)

            loop = asyncio.get_event_loop()

            if kind in ("gif", "video"):
                if bg_url == "from_file":
                    ext = self.db.get("LazyQuotes", "bg_ext", ".mp4")
                else:
                    ext = "." + mime.split("/")[-1] if "/" in mime else ".mp4"
                if ext not in (".mp4", ".webm", ".mov", ".gif", ".avi", ".mkv"):
                    ext = ".mp4"

                out_path = await loop.run_in_executor(
                    None, _render_video,
                    bg_bytes, text, author, avatar_data, ext, font_path, emoji_font_path, timestamp,
                )
                try:
                    sent = await message.client.send_file(
                        message.peer_id,
                        out_path,
                        reply_to=message.reply_to_msg_id,
                    )
                finally:
                    os.unlink(out_path)

                # убираем из сохранённых гифок всегда при отправке видео/гиф
                if sent and sent.media and hasattr(sent.media, "document"):
                    await _unsave_gif(message.client, sent)
            else:
                img_bytes = await loop.run_in_executor(
                    None, _render_photo,
                    bg_bytes, text, author, avatar_data, font_path, emoji_font_path, timestamp,
                )
                buf = io.BytesIO(img_bytes)
                buf.name = "quote.jpg"
                await message.client.send_file(
                    message.peer_id,
                    buf,
                    reply_to=message.reply_to_msg_id,
                )

            await message.delete()

        except Exception as e:
            await utils.answer(message, self.strings("error").format(str(e)))
