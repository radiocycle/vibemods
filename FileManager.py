__version__ = (1, 0, 0)

# meta developer: @arachnophiliac

import asyncio
import contextlib
import os
import re
import stat
import sys
import time
from pathlib import Path

try:
    from .. import loader, utils
    from ..inline.types import InlineCall
except ImportError:
    from heroku import loader, utils
    from heroku.inline.types import InlineCall
from telethon.tl.types import Message


MODE_RE = re.compile(r"^[0-7]{3,4}$")
SCRIPT_INTERPRETERS = {
    ".py": [sys.executable],
    ".sh": ["/bin/sh"],
    ".bash": ["/bin/bash"],
}


@loader.tds
class FileManagerMod(loader.Module):
    """Inline file manager with save, send, run, chmod, and delete actions."""

    strings = {
        "name": "FileManager",
        "no_reply_file": "Reply to a file or media message.",
        "saved": "Saved: <code>{path}</code>",
        "save_failed": "Save failed: <code>{error}</code>",
        "bad_path": "Invalid path.",
        "not_found": "Path not found.",
        "not_file": "This action requires a file.",
        "not_dir": "This action requires a directory.",
        "permission_error": "Permission denied.",
        "empty_dir": "Directory is empty.",
        "delete_confirm": "Delete <code>{path}</code>?",
        "deleted": "Deleted: <code>{path}</code>",
        "delete_failed": "Delete failed: <code>{error}</code>",
        "chmod_prompt": "Enter numeric mode, for example 644 or 755",
        "chmod_done": "Mode changed to <code>{mode}</code>.",
        "chmod_bad": "Use numeric chmod mode: 644, 755, 0600.",
        "run_not_allowed": "File is not executable and has no known script extension.",
        "run_started": "Running <code>{path}</code>...",
        "run_timeout": "Process timed out.",
        "send_done": "File sent.",
        "send_failed": "Send failed: <code>{error}</code>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "base_path",
                "~",
                "Base path for .fman relative paths",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "save_path",
                "~/saved_files",
                "Directory where .fsave stores replied files",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "list_limit",
                10,
                "Entries per inline page",
                validator=loader.validators.Integer(minimum=4, maximum=30),
            ),
            loader.ConfigValue(
                "run_timeout",
                20,
                "Run timeout in seconds",
                validator=loader.validators.Integer(minimum=1, maximum=300),
            ),
        )

    async def client_ready(self, client, db):
        self._client = client

    def _button(self, text: str, callback, args=(), style=None) -> dict:
        button = {"text": text, "callback": callback, "args": tuple(args)}
        if style:
            button["style"] = style
        return button

    def _input_button(self, text: str, prompt: str, handler, args=(), style=None) -> dict:
        button = {
            "text": text,
            "input": prompt,
            "handler": handler,
            "args": tuple(args),
        }
        if style:
            button["style"] = style
        return button

    async def _safe_answer(self, call: InlineCall, text: str | None = None, **kwargs):
        with contextlib.suppress(Exception):
            if text is None:
                await call.answer()
            else:
                await call.answer(text, **kwargs)

    def _base_path(self) -> Path:
        return Path(str(self.config["base_path"] or "~")).expanduser().resolve(strict=False)

    def _save_path(self) -> Path:
        return Path(str(self.config["save_path"] or "~/saved_files")).expanduser().resolve(strict=False)

    def _resolve_path(self, raw: str, base: Path | None = None) -> Path | None:
        if raw is None or "\x00" in str(raw):
            return None
        value = str(raw).strip()
        if not value:
            return None
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = (base or self._base_path()) / path
        try:
            return path.resolve(strict=False)
        except Exception:
            return None

    def _safe_filename(self, name: str | None, fallback: str = "telegram_file") -> str:
        name = os.path.basename(str(name or "").replace("\x00", "")).strip()
        if not name or name in {".", ".."}:
            name = fallback
        return name[:180]

    def _unique_destination(self, directory: Path, filename: str) -> Path:
        dest = directory / self._safe_filename(filename)
        if not dest.exists():
            return dest

        stem = dest.stem or "file"
        suffix = dest.suffix
        for idx in range(1, 1000):
            candidate = directory / f"{stem}_{idx}{suffix}"
            if not candidate.exists():
                return candidate
        return directory / f"{stem}_{int(time.time())}{suffix}"

    def _reply_filename(self, message: Message) -> str:
        file_obj = getattr(message, "file", None)
        name = getattr(file_obj, "name", None)
        if name:
            return self._safe_filename(name)

        ext = getattr(file_obj, "ext", None) or ""
        if ext and not str(ext).startswith("."):
            ext = f".{ext}"
        return self._safe_filename(f"telegram_file_{getattr(message, 'id', int(time.time()))}{ext}")

    def _format_size(self, size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
            value /= 1024
        return f"{size} B"

    def _format_mode(self, mode: int) -> str:
        return oct(stat.S_IMODE(mode))[2:].zfill(3)

    def _entry_label(self, path: Path) -> str:
        prefix = "[D]" if path.is_dir() else "[F]"
        name = path.name or str(path)
        if len(name) > 38:
            name = name[:35] + "..."
        return f"{prefix} {name}"

    def _path_text(self, path: Path) -> str:
        return utils.escape_html(str(path))

    def _stat_text(self, path: Path) -> str:
        try:
            st = path.stat()
        except PermissionError:
            return self.strings["permission_error"]
        except FileNotFoundError:
            return self.strings["not_found"]

        kind = "directory" if path.is_dir() else "file"
        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
        return (
            f"<b>{utils.escape_html(path.name or str(path))}</b>\n\n"
            f"Path: <code>{self._path_text(path)}</code>\n"
            f"Type: <code>{kind}</code>\n"
            f"Size: <code>{self._format_size(st.st_size)}</code>\n"
            f"Mode: <code>{self._format_mode(st.st_mode)}</code>\n"
            f"Modified: <code>{utils.escape_html(mtime)}</code>"
        )

    def _parent_path(self, path: Path) -> Path:
        parent = path.parent
        return parent if parent != path else path

    def _page_count(self, total: int) -> int:
        per_page = int(self.config["list_limit"])
        return max(1, (total + per_page - 1) // per_page)

    def _dir_entries(self, path: Path) -> list[Path]:
        entries = list(path.iterdir())
        entries.sort(key=lambda item: (not item.is_dir(), item.name.lower()))
        return entries

    async def _dir_view(self, path: Path, page: int = 0) -> tuple[str, list]:
        if not path.exists():
            return self.strings["not_found"], [[{"text": "Close", "action": "close"}]]
        if not path.is_dir():
            return self._file_view(path)

        try:
            entries = self._dir_entries(path)
        except PermissionError:
            entries = []
            text = (
                f"<b>FileManager</b>\n\n"
                f"Path: <code>{self._path_text(path)}</code>\n\n"
                f"{self.strings['permission_error']}"
            )
        else:
            text = (
                f"<b>FileManager</b>\n\n"
                f"Path: <code>{self._path_text(path)}</code>\n"
                f"Entries: <code>{len(entries)}</code>"
            )
            if not entries:
                text += f"\n\n{self.strings['empty_dir']}"

        per_page = int(self.config["list_limit"])
        total_pages = self._page_count(len(entries))
        page = max(0, min(int(page), total_pages - 1))
        start = page * per_page
        rows = []
        for item in entries[start : start + per_page]:
            rows.append([self._button(self._entry_label(item), self._open_path, (str(item), 0))])

        nav = []
        if page > 0:
            nav.append(self._button("Prev", self._open_path, (str(path), page - 1)))
        nav.append(self._button(f"{page + 1}/{total_pages}", self._open_path, (str(path), page)))
        if page < total_pages - 1:
            nav.append(self._button("Next", self._open_path, (str(path), page + 1)))
        rows.append(nav)

        rows.append(
            [
                self._button("Up", self._open_path, (str(self._parent_path(path)), 0), "primary"),
                self._input_button("Jump", "Enter path", self._jump_input, (str(path),), "primary"),
            ]
        )
        rows.append([{"text": "Close", "action": "close"}])
        return text, rows

    def _file_view(self, path: Path) -> tuple[str, list]:
        rows = []
        if path.is_file():
            rows.append(
                [
                    self._button("Send", self._send_file, (str(path),), "success"),
                    self._button("Run", self._run_file, (str(path),), "primary"),
                ]
            )
        rows.append(
            [
                self._input_button("Chmod", self.strings["chmod_prompt"], self._chmod_input, (str(path),), "primary"),
                self._button("Delete", self._confirm_delete, (str(path),), "danger"),
            ]
        )
        rows.append(
            [
                self._button("Back", self._open_path, (str(self._parent_path(path)), 0), "primary"),
                {"text": "Close", "action": "close"},
            ]
        )
        return self._stat_text(path), rows

    async def _open_path(self, call: InlineCall, raw_path: str, page: int = 0):
        await self._safe_answer(call)
        path = self._resolve_path(raw_path)
        if not path:
            return await call.edit(self.strings["bad_path"], reply_markup=[[{"text": "Close", "action": "close"}]])
        text, markup = await self._dir_view(path, page)
        await call.edit(text, reply_markup=markup)

    async def _jump_input(self, call: InlineCall, data, current_path: str):
        base = self._resolve_path(current_path) or self._base_path()
        path = self._resolve_path(str(data or ""), base=base)
        if not path:
            return await self._safe_answer(call, self.strings["bad_path"], show_alert=True)
        text, markup = await self._dir_view(path, 0)
        await call.edit(text, reply_markup=markup)

    async def _confirm_delete(self, call: InlineCall, raw_path: str):
        await self._safe_answer(call)
        path = self._resolve_path(raw_path)
        if not path or not path.exists():
            return await self._safe_answer(call, self.strings["not_found"], show_alert=True)
        await call.edit(
            self.strings["delete_confirm"].format(path=self._path_text(path)),
            reply_markup=[
                [
                    self._button("Delete", self._delete_path, (str(path),), "danger"),
                    self._button("Cancel", self._open_path, (str(path), 0), "primary"),
                ],
                [{"text": "Close", "action": "close"}],
            ],
        )

    async def _delete_path(self, call: InlineCall, raw_path: str):
        path = self._resolve_path(raw_path)
        if not path or not path.exists():
            return await self._safe_answer(call, self.strings["not_found"], show_alert=True)

        parent = self._parent_path(path)
        try:
            if path.is_dir():
                path.rmdir()
            else:
                path.unlink()
        except Exception as e:
            return await self._safe_answer(
                call,
                self.strings["delete_failed"].format(error=utils.escape_html(str(e))),
                show_alert=True,
            )

        await self._safe_answer(
            call,
            self.strings["deleted"].format(path=str(path)),
            show_alert=False,
        )
        text, markup = await self._dir_view(parent, 0)
        await call.edit(text, reply_markup=markup)

    async def _chmod_input(self, call: InlineCall, data, raw_path: str):
        mode_text = str(data or "").strip()
        if not MODE_RE.fullmatch(mode_text):
            return await self._safe_answer(call, self.strings["chmod_bad"], show_alert=True)

        path = self._resolve_path(raw_path)
        if not path or not path.exists():
            return await self._safe_answer(call, self.strings["not_found"], show_alert=True)

        try:
            os.chmod(path, int(mode_text, 8))
        except Exception as e:
            return await self._safe_answer(call, utils.escape_html(str(e)), show_alert=True)

        await self._safe_answer(
            call,
            self.strings["chmod_done"].format(mode=mode_text),
            show_alert=False,
        )
        text, markup = await self._dir_view(path, 0)
        await call.edit(text, reply_markup=markup)

    async def _send_file(self, call: InlineCall, raw_path: str):
        await self._safe_answer(call)
        path = self._resolve_path(raw_path)
        if not path or not path.is_file():
            return await self._safe_answer(call, self.strings["not_file"], show_alert=True)

        chat_id = getattr(call, "chat_id", None)
        if chat_id is None:
            return await self._safe_answer(call, "Chat id is unavailable.", show_alert=True)

        try:
            await self._client.send_file(
                chat_id,
                str(path),
                caption=f"<code>{self._path_text(path)}</code>",
            )
        except Exception as e:
            return await self._safe_answer(
                call,
                self.strings["send_failed"].format(error=utils.escape_html(str(e))),
                show_alert=True,
            )
        await self._safe_answer(call, self.strings["send_done"], show_alert=False)

    def _run_argv(self, path: Path) -> list[str] | None:
        if path.suffix.lower() in SCRIPT_INTERPRETERS:
            return [*SCRIPT_INTERPRETERS[path.suffix.lower()], str(path)]
        if os.access(path, os.X_OK):
            return [str(path)]
        return None

    def _format_run_output(self, path: Path, rc: int, stdout: str, stderr: str) -> str:
        output = "\n".join(part for part in (stdout, stderr) if part).strip()
        if not output:
            output = f"rc={rc}"
        else:
            output = f"rc={rc}\n{output}"
        if len(output) > 3200:
            output = output[:3200] + "\n..."
        return (
            f"<b>Run: {utils.escape_html(path.name)}</b>\n\n"
            f"<blockquote><code>{utils.escape_html(output)}</code></blockquote>"
        )

    async def _run_file(self, call: InlineCall, raw_path: str):
        await self._safe_answer(call)
        path = self._resolve_path(raw_path)
        if not path or not path.is_file():
            return await self._safe_answer(call, self.strings["not_file"], show_alert=True)

        argv = self._run_argv(path)
        if not argv:
            return await self._safe_answer(call, self.strings["run_not_allowed"], show_alert=True)

        await call.edit(
            self.strings["run_started"].format(path=self._path_text(path)),
            reply_markup=None,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(path.parent),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=int(self.config["run_timeout"]),
            )
        except asyncio.TimeoutError:
            with contextlib.suppress(Exception):
                proc.kill()
                await proc.wait()
            text = self.strings["run_timeout"]
        except FileNotFoundError as e:
            text = utils.escape_html(str(e))
        else:
            text = self._format_run_output(
                path,
                proc.returncode,
                stdout.decode(errors="ignore"),
                stderr.decode(errors="ignore"),
            )

        await call.edit(
            text,
            reply_markup=[
                [
                    self._button("Back", self._open_path, (str(path), 0), "primary"),
                    {"text": "Close", "action": "close"},
                ]
            ],
        )

    @loader.command(ru_doc="[имя] - сохранить replied файл в save_path из конфига")
    async def fsave(self, message: Message):
        """Save replied file/media into configured save_path."""
        reply = await message.get_reply_message()
        if not reply or not getattr(reply, "file", None):
            return await utils.answer(message, self.strings["no_reply_file"])

        save_dir = self._save_path()
        try:
            save_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return await utils.answer(
                message,
                self.strings["save_failed"].format(error=utils.escape_html(str(e))),
            )

        args = utils.get_args_raw(message).strip()
        filename = self._safe_filename(args) if args else self._reply_filename(reply)
        dest = self._unique_destination(save_dir, filename)

        try:
            path = await self._client.download_media(reply, file=str(dest))
        except Exception as e:
            return await utils.answer(
                message,
                self.strings["save_failed"].format(error=utils.escape_html(str(e))),
            )

        return await utils.answer(
            message,
            self.strings["saved"].format(path=utils.escape_html(str(path or dest))),
        )

    @loader.command(ru_doc="[путь] - inline file manager")
    async def fman(self, message: Message):
        """Open inline file manager."""
        raw = utils.get_args_raw(message).strip()
        path = self._resolve_path(raw) if raw else self._base_path()
        if not path:
            return await utils.answer(message, self.strings["bad_path"])

        text, markup = await self._dir_view(path, 0)
        await self.inline.form(
            text=text,
            message=message,
            reply_markup=markup,
        )
