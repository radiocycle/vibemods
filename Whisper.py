__version__ = (1, 0, 0)

# meta developer: @arachnophiliac

import contextlib
import re

try:
    from .. import loader, utils
    from ..inline.types import InlineCall
except ImportError:
    from heroku import loader, utils
    from heroku.inline.types import InlineCall

from telethon.tl.types import User


TARGET_RE = re.compile(r"^(?:@[\w\d_]{3,}|-?\d+|https?://t\.me/[\w\d_]+|t\.me/[\w\d_]+|tg://user\?id=\d+)$", re.I)


@loader.tds
class WhisperMod(loader.Module):
    """Private inline whispers shown only to the sender and target."""

    strings = {
        "name": "Whisper",
        "usage": (
            "Usage:\n"
            "@your_bot whisper @user text\n"
            "@your_bot whisper 123456 text"
        ),
        "empty_text": "Whisper text is empty.",
        "target_not_found": "Could not resolve target user.",
        "target_is_chat": "Target must be a user.",
        "sent": (
            "<b>Whisper</b>\n"
            "For: <code>{target}</code>\n\n"
            "Only sender and target can open it."
        ),
        "button": "Read whisper",
        "denied": "This whisper is not for you.",
        "truncated": "\n\n[truncated]",
        "inline_title": "Whisper to {target}",
        "inline_description": "Only sender and target can open it.",
    }

    strings_ru = {
        "usage": (
            "Использование:\n"
            "@твой_бот whisper @user текст\n"
            "@твой_бот whisper 123456 текст"
        ),
        "empty_text": "Текст шепота пустой.",
        "target_not_found": "Не смог найти адресата.",
        "target_is_chat": "Адресатом должен быть пользователь.",
        "sent": (
            "<b>Шепот</b>\n"
            "Кому: <code>{target}</code>\n\n"
            "Открыть могут только отправитель и адресат."
        ),
        "button": "Прочитать шепот",
        "denied": "Этот шепот не для тебя.",
        "truncated": "\n\n[обрезано]",
        "inline_title": "Шепот для {target}",
        "inline_description": "Открыть могут только отправитель и адресат.",
    }

    async def client_ready(self, client, db):
        self.client = client
        self._client = client
        self._owner_id = None
        with contextlib.suppress(Exception):
            me = await client.get_me()
            self._owner_id = self._as_int(getattr(me, "id", None))

    def _str(self, key: str) -> str:
        strings = getattr(self, "strings", {})
        if callable(strings):
            return strings(key)
        return strings.get(key, key)

    def _as_int(self, value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _looks_like_target(self, token: str) -> bool:
        return bool(TARGET_RE.fullmatch((token or "").strip()))

    def _normalize_target(self, token: str):
        value = (token or "").strip()
        value = value.removeprefix("https://").removeprefix("http://")
        if value.startswith("t.me/"):
            value = "@" + value.split("/", 1)[1].strip("/")
        if value.lower().startswith("tg://user?id="):
            value = value.split("=", 1)[1]
        if value.lstrip("-").isdigit():
            return int(value)
        return value

    def _caller_id(self, call: InlineCall) -> int | None:
        for attr in ("sender_id", "user_id"):
            user_id = self._as_int(getattr(call, attr, None))
            if user_id is not None:
                return user_id

        for attr in ("from_user", "user", "query"):
            source = getattr(call, attr, None)
            if source is None:
                continue
            if isinstance(source, dict):
                user_id = self._as_int(source.get("id") or source.get("user_id"))
            else:
                user_id = self._as_int(
                    getattr(source, "id", None) or getattr(source, "user_id", None)
                )
            if user_id is not None:
                return user_id

        return None

    def _target_label(self, user, *, escape_html: bool = False) -> str:
        username = getattr(user, "username", None)
        if username:
            label = f"@{username}"
            return utils.escape_html(label) if escape_html else label

        parts = [
            getattr(user, "first_name", None),
            getattr(user, "last_name", None),
        ]
        name = " ".join(str(part) for part in parts if part).strip()
        if name:
            return utils.escape_html(name) if escape_html else name

        return str(getattr(user, "id", "unknown"))

    def _is_user(self, entity) -> bool:
        return isinstance(entity, User)

    def _popup_text(self, text: str) -> str:
        limit = 190
        value = str(text or "")
        if len(value) <= limit:
            return value
        suffix = self._str("truncated")
        return value[: max(1, limit - len(suffix))] + suffix

    async def _resolve_inline_request(self, raw: str):
        raw = (raw or "").strip()
        if not raw:
            return None, "", "usage"

        parts = raw.split(maxsplit=1)
        if len(parts) != 2:
            return None, "", "usage"

        target_ref = self._normalize_target(parts[0])
        text = parts[1].strip()
        try:
            target = await self.client.get_entity(target_ref)
        except Exception:
            return None, "", "target_not_found"
        return target, text, None

    def _build_markup(self, text: str, allowed_ids: tuple[int, ...]) -> list:
        allowed = list(allowed_ids)
        return [
            [
                {
                    "text": self._str("button"),
                    "callback": self._show_whisper,
                    "args": (text, allowed_ids),
                    "always_allow": allowed,
                    "force_me": True,
                }
            ]
        ]

    def _build_inline_result(self, target, text: str, allowed_ids: tuple[int, ...]) -> dict:
        target_label = self._target_label(target)
        target_html_label = self._target_label(target, escape_html=True)
        allowed = list(allowed_ids)
        return {
            "title": self._str("inline_title").format(target=target_label),
            "description": self._str("inline_description"),
            "message": self._str("sent").format(target=target_html_label),
            "reply_markup": self._build_markup(text, allowed_ids),
            "always_allow": allowed,
            "force_me": True,
        }

    def _allowed_ids(self, target_id: int, sender_id: int | None = None) -> tuple[int, ...]:
        owner_id = self._owner_id or sender_id
        return tuple(user_id for user_id in (owner_id, target_id) if user_id is not None)

    async def _show_whisper(self, call: InlineCall, text: str, allowed_ids: tuple[int, ...]):
        caller_id = self._caller_id(call)
        if caller_id not in set(allowed_ids):
            return await call.answer(self._str("denied"), show_alert=True)

        await call.answer(self._popup_text(text), show_alert=True)

    async def whisper_inline_handler(self, query):
        """<@user|id> <text> - private popup whisper."""
        raw = (getattr(query, "args", None) or getattr(query, "query", "") or "").strip()
        target, text, error = await self._resolve_inline_request(raw)
        if error:
            return {
                "title": "Whisper",
                "description": self._str(error),
                "message": self._str(error),
            }
        if not text:
            return {
                "title": "Whisper",
                "description": self._str("empty_text"),
                "message": self._str("empty_text"),
            }

        target_id = self._as_int(getattr(target, "id", None))
        if not self._is_user(target) or target_id is None:
            return {
                "title": "Whisper",
                "description": self._str("target_is_chat"),
                "message": self._str("target_is_chat"),
            }

        allowed_ids = self._allowed_ids(target_id, sender_id=self._caller_id(query))
        if not allowed_ids:
            return {
                "title": "Whisper",
                "description": self._str("target_not_found"),
                "message": self._str("target_not_found"),
            }

        return self._build_inline_result(target, text, allowed_ids)
