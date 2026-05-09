__version__ = (1, 0, 0)

# meta developer: @arachnophiliac

import asyncio
import contextlib
import os
import re

try:
    from .. import loader, utils
    from ..inline.types import InlineCall
except ImportError:
    from heroku import loader, utils
    from heroku.inline.types import InlineCall
from telethon.tl.types import Message


UNIT_RE = re.compile(
    r"^[A-Za-z0-9_.@:+-]+\."
    r"(service|socket|timer|target|path|mount|automount|swap|slice|scope)$"
)
UNIT_TYPES = (
    ".service",
    ".socket",
    ".timer",
    ".target",
    ".path",
    ".mount",
    ".automount",
    ".swap",
    ".slice",
    ".scope",
)
PASSWORD_MARKERS = (
    "a password is required",
    "password is required",
    "sudo: a password",
    "sudo: no tty present",
    "authentication is required",
    "incorrect password",
    "sorry, try again",
)


@loader.tds
class SystemdManagerMod(loader.Module):
    """Inline manager for selected systemd units."""

    strings = {
        "name": "SystemdManager",
        "empty": (
            "<b>Systemd units</b>\n\n"
            "Список пуст. Нажми <b>Add unit</b> и введи имя, например "
            "<code>nginx.service</code> или <code>nginx</code>."
        ),
        "main": "<b>Systemd units</b>\n\n{units}",
        "unit": (
            "<b>{unit}</b>\n\n"
            "Active: <code>{active}</code>\n"
            "Enabled: <code>{enabled}</code>\n"
            "Load: <code>{load}</code>{message}"
        ),
        "running": "Выполняю <code>{action}</code> для <code>{unit}</code>...",
        "view_running": "Загружаю <code>{view}</code> для <code>{unit}</code>...",
        "need_password": (
            "<b>{unit}</b>\n\n"
            "Для <code>{action}</code> нужен sudo-пароль. Пароль будет "
            "использован один раз и не сохранится."
        ),
        "bad_unit": (
            "Некорректное имя юнита. Используй имя systemd unit без пробелов "
            "и shell-символов, например <code>nginx.service</code>."
        ),
        "added": "Добавлено: <code>{unit}</code>",
        "removed": "Удалено из списка: <code>{unit}</code>",
        "not_found": "Юнит не найден в списке.",
        "password_failed": "Пароль не подошёл или sudo отклонил команду.",
        "timeout": "Команда превысила таймаут.",
    }

    COMMAND_TIMEOUT = 35
    MAX_OUTPUT = 900
    VIEW_OUTPUT = 3200

    async def client_ready(self, client, db):
        self._client = client
        self._units = self._load_units()

    def _load_units(self) -> list[str]:
        units = self.get("units", [])
        if not isinstance(units, list):
            return []

        normalized = []
        for unit in units:
            valid = self._normalize_unit_name(str(unit or ""))
            if valid and valid not in normalized:
                normalized.append(valid)
        return normalized

    def _save_units(self):
        self.set("units", self._units_list())

    def _units_list(self) -> list[str]:
        units = getattr(self, "_units", None)
        if not isinstance(units, list):
            units = self._load_units()
            self._units = units
        return units

    def _normalize_unit_name(self, raw: str) -> str | None:
        unit = (raw or "").strip()
        if not unit:
            return None

        if any(ch.isspace() for ch in unit):
            return None

        if not any(unit.endswith(suffix) for suffix in UNIT_TYPES):
            unit = f"{unit}.service"

        if len(unit) > 256 or unit.startswith("-") or not UNIT_RE.fullmatch(unit):
            return None
        return unit

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

    def _main_markup(self) -> list:
        rows = []
        for unit in self._units_list():
            rows.append([self._button(unit, self._unit_menu, (unit,), "primary")])

        rows.append(
            [
                self._input_button(
                    "Add unit",
                    "Введите имя systemd unit, например nginx.service",
                    self._add_unit_input,
                    (),
                    "success",
                ),
                self._button("Del unit", self._delete_menu, (), "danger"),
            ]
        )
        rows.append([{"text": "Close", "action": "close"}])
        return rows

    async def _main_text(self) -> str:
        units = self._units_list()
        if not units:
            return self.strings["empty"]

        lines = []
        for unit in units:
            state = await self._unit_state(unit)
            lines.append(
                "• <code>{}</code> — <b>{}</b> / <code>{}</code>".format(
                    utils.escape_html(unit),
                    utils.escape_html(state["active"]),
                    utils.escape_html(state["enabled"]),
                )
            )
        return self.strings["main"].format(units="\n".join(lines))

    async def _refresh_main(self, call: InlineCall):
        await call.edit(await self._main_text(), reply_markup=self._main_markup())

    async def _safe_answer(self, call: InlineCall, text: str | None = None, **kwargs):
        with contextlib.suppress(Exception):
            if text is None:
                await call.answer()
            else:
                await call.answer(text, **kwargs)

    async def _run_command(
        self,
        executable: str,
        args: list[str],
        password: str | None = None,
        sudo: bool = False,
    ) -> tuple[int, str, str]:
        cmd = [executable, *args]
        stdin_data = None

        if sudo and os.geteuid() != 0:
            if password is None:
                cmd = ["sudo", "-n", *cmd]
            else:
                cmd = ["sudo", "-S", "-p", "", *cmd]
                stdin_data = f"{password}\n".encode()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if stdin_data is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return 127, "", f"{cmd[0]} not found"

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=stdin_data),
                timeout=self.COMMAND_TIMEOUT,
            )
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()
            return 124, "", self.strings["timeout"]

        return (
            proc.returncode,
            stdout.decode(errors="ignore").strip(),
            stderr.decode(errors="ignore").strip(),
        )

    async def _run_systemctl(
        self,
        args: list[str],
        password: str | None = None,
        sudo: bool = False,
    ) -> tuple[int, str, str]:
        return await self._run_command("systemctl", args, password=password, sudo=sudo)

    async def _run_journalctl(
        self,
        args: list[str],
        password: str | None = None,
        sudo: bool = False,
    ) -> tuple[int, str, str]:
        return await self._run_command("journalctl", args, password=password, sudo=sudo)

    def _password_required(self, text: str) -> bool:
        lowered = (text or "").lower()
        return any(marker in lowered for marker in PASSWORD_MARKERS)

    def _format_command_result(self, rc: int, stdout: str, stderr: str) -> str:
        output = "\n".join(part for part in (stdout, stderr) if part).strip()
        if not output:
            return f"\n\nResult: <code>rc={rc}</code>"

        if len(output) > self.MAX_OUTPUT:
            output = output[: self.MAX_OUTPUT] + "\n..."
        return "\n\n<blockquote><code>{}</code></blockquote>".format(
            utils.escape_html(output)
        )

    async def _unit_state(self, unit: str) -> dict[str, str]:
        active_rc, active, _active_err = await self._run_systemctl(
            ["is-active", unit],
            sudo=False,
        )
        enabled_rc, enabled, enabled_err = await self._run_systemctl(
            ["is-enabled", unit],
            sudo=False,
        )
        show_rc, show, show_err = await self._run_systemctl(
            [
                "show",
                unit,
                "--property=LoadState",
                "--property=ActiveState",
                "--property=SubState",
                "--property=UnitFileState",
            ],
            sudo=False,
        )

        details = {}
        for line in show.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                details[key] = value or "-"

        return {
            "active": active if active_rc == 0 and active else details.get("ActiveState", "inactive"),
            "enabled": enabled if enabled_rc == 0 and enabled else enabled or enabled_err or details.get("UnitFileState", "unknown"),
            "load": details.get("LoadState", "unknown" if show_rc else "-"),
            "sub": details.get("SubState", "-"),
            "error": show_err,
        }

    def _unit_markup(self, unit: str, state: dict[str, str]) -> list:
        is_active = state["active"] == "active"
        is_enabled = state["enabled"] == "enabled"
        start_stop_action = "stop" if is_active else "start"
        enable_action = "disable" if is_enabled else "enable"

        return [
            [
                self._button(
                    "Stop" if is_active else "Start",
                    self._operate,
                    (unit, start_stop_action),
                    "danger" if is_active else "success",
                ),
                self._button("Restart", self._operate, (unit, "restart"), "primary"),
            ],
            [
                self._button(
                    "Disable" if is_enabled else "Enable",
                    self._operate,
                    (unit, enable_action),
                    "danger" if is_enabled else "success",
                ),
                self._button("Удалить", self._remove_unit, (unit,), "danger"),
            ],
            [
                self._button("Status", self._view_unit_output, (unit, "status"), "primary"),
                self._button("Tail", self._view_unit_output, (unit, "tail"), "primary"),
            ],
            [
                self._button("Back", self._back_to_main, (), "primary"),
                {"text": "Close", "action": "close"},
            ],
        ]

    async def _unit_text(self, unit: str, message: str = "") -> tuple[str, list]:
        state = await self._unit_state(unit)
        extra = ""
        if message:
            extra = message
        elif state.get("sub") and state["sub"] != "-":
            extra = f"\nSub: <code>{utils.escape_html(state['sub'])}</code>"

        text = self.strings["unit"].format(
            unit=utils.escape_html(unit),
            active=utils.escape_html(state["active"]),
            enabled=utils.escape_html(state["enabled"]),
            load=utils.escape_html(state["load"]),
            message=extra,
        )
        return text, self._unit_markup(unit, state)

    async def _unit_menu(self, call: InlineCall, unit: str, message: str = ""):
        unit = self._normalize_unit_name(unit)
        if not unit or unit not in self._units_list():
            return await self._safe_answer(call, self.strings["not_found"], show_alert=True)
        await self._safe_answer(call)
        text, markup = await self._unit_text(unit, message)
        await call.edit(text, reply_markup=markup)

    async def _password_prompt(self, call: InlineCall, unit: str, action: str, stderr: str):
        details = ""
        if stderr:
            details = "\n\n<blockquote><code>{}</code></blockquote>".format(
                utils.escape_html(stderr[: self.MAX_OUTPUT])
            )
        await call.edit(
            self.strings["need_password"].format(
                unit=utils.escape_html(unit),
                action=utils.escape_html(action),
            )
            + details,
            reply_markup=[
                [
                    self._input_button(
                        "Ввести пароль",
                        f"sudo password for {action} {unit}",
                        self._password_input,
                        (unit, action),
                        "primary",
                    )
                ],
                [
                    self._button("Back", self._unit_menu, (unit,), "primary"),
                    {"text": "Close", "action": "close"},
                ],
            ],
        )

    async def _operate(
        self,
        call: InlineCall,
        unit: str,
        action: str,
        password: str | None = None,
    ):
        unit = self._normalize_unit_name(unit)
        if not unit or unit not in self._units_list():
            return await self._safe_answer(call, self.strings["not_found"], show_alert=True)
        if action not in {"start", "stop", "restart", "enable", "disable"}:
            return await self._safe_answer(call, "Unknown action.", show_alert=True)

        await self._safe_answer(call)
        await call.edit(
            self.strings["running"].format(
                action=utils.escape_html(action),
                unit=utils.escape_html(unit),
            ),
            reply_markup=None,
        )

        rc, stdout, stderr = await self._run_systemctl(
            [action, unit],
            password=password,
            sudo=True,
        )

        combined_output = "\n".join(part for part in (stdout, stderr) if part)

        if password is None and self._password_required(combined_output):
            return await self._password_prompt(call, unit, action, stderr)

        if password is not None and rc != 0 and self._password_required(combined_output):
            return await self._password_prompt(
                call,
                unit,
                action,
                self.strings["password_failed"],
            )

        message = self._format_command_result(rc, stdout, stderr)
        await self._unit_menu(call, unit, message)

    async def _password_input(self, call: InlineCall, data, unit: str, action: str):
        password = str(data or "")
        if not password:
            return await self._password_prompt(call, unit, action, "")
        await self._operate(call, unit, action, password=password)

    def _view_label(self, view: str) -> str:
        return "tail logs" if view == "tail" else "status"

    def _view_markup(self, unit: str, view: str) -> list:
        return [
            [
                self._button("Refresh", self._view_unit_output, (unit, view), "primary"),
                self._button("Back", self._unit_menu, (unit,), "primary"),
            ],
            [{"text": "Close", "action": "close"}],
        ]

    def _format_view_text(self, unit: str, view: str, rc: int, stdout: str, stderr: str) -> str:
        title = "journalctl tail" if view == "tail" else "systemctl status"
        output = "\n".join(part for part in (stdout, stderr) if part).strip()
        if not output:
            output = f"rc={rc}"
        elif rc != 0:
            output = f"rc={rc}\n{output}"

        if len(output) > self.VIEW_OUTPUT:
            output = output[-self.VIEW_OUTPUT :] if view == "tail" else output[: self.VIEW_OUTPUT]
            output = ("...\n" + output) if view == "tail" else (output + "\n...")

        return (
            f"<b>{utils.escape_html(title)}: {utils.escape_html(unit)}</b>\n\n"
            f"<blockquote><code>{utils.escape_html(output)}</code></blockquote>"
        )

    async def _run_view_command(
        self,
        unit: str,
        view: str,
        password: str | None = None,
    ) -> tuple[int, str, str]:
        if view == "status":
            return await self._run_systemctl(
                ["status", unit, "--no-pager", "--lines=40"],
                password=password,
                sudo=password is not None,
            )
        if view == "tail":
            return await self._run_journalctl(
                ["-u", unit, "-n", "120", "--no-pager"],
                password=password,
                sudo=True,
            )
        return 1, "", "Unknown view."

    async def _view_password_prompt(
        self,
        call: InlineCall,
        unit: str,
        view: str,
        stderr: str,
    ):
        details = ""
        if stderr:
            details = "\n\n<blockquote><code>{}</code></blockquote>".format(
                utils.escape_html(stderr[: self.MAX_OUTPUT])
            )
        await call.edit(
            self.strings["need_password"].format(
                unit=utils.escape_html(unit),
                action=utils.escape_html(self._view_label(view)),
            )
            + details,
            reply_markup=[
                [
                    self._input_button(
                        "Ввести пароль",
                        f"sudo password for {self._view_label(view)} {unit}",
                        self._view_password_input,
                        (unit, view),
                        "primary",
                    )
                ],
                [
                    self._button("Back", self._unit_menu, (unit,), "primary"),
                    {"text": "Close", "action": "close"},
                ],
            ],
        )

    async def _view_unit_output(
        self,
        call: InlineCall,
        unit: str,
        view: str,
        password: str | None = None,
    ):
        unit = self._normalize_unit_name(unit)
        if not unit or unit not in self._units_list():
            return await self._safe_answer(call, self.strings["not_found"], show_alert=True)
        if view not in {"status", "tail"}:
            return await self._safe_answer(call, "Unknown view.", show_alert=True)

        await self._safe_answer(call)
        await call.edit(
            self.strings["view_running"].format(
                view=utils.escape_html(self._view_label(view)),
                unit=utils.escape_html(unit),
            ),
            reply_markup=None,
        )

        rc, stdout, stderr = await self._run_view_command(unit, view, password=password)
        combined_output = "\n".join(part for part in (stdout, stderr) if part)

        if password is None and self._password_required(combined_output):
            return await self._view_password_prompt(call, unit, view, stderr)

        if password is not None and rc != 0 and self._password_required(combined_output):
            return await self._view_password_prompt(
                call,
                unit,
                view,
                self.strings["password_failed"],
            )

        await call.edit(
            self._format_view_text(unit, view, rc, stdout, stderr),
            reply_markup=self._view_markup(unit, view),
        )

    async def _view_password_input(self, call: InlineCall, data, unit: str, view: str):
        password = str(data or "")
        if not password:
            return await self._view_password_prompt(call, unit, view, "")
        await self._view_unit_output(call, unit, view, password=password)

    async def _add_unit_input(self, call: InlineCall, data):
        unit = self._normalize_unit_name(str(data or ""))
        if not unit:
            return await self._safe_answer(call, self.strings["bad_unit"], show_alert=True)

        units = self._units_list()
        if unit not in units:
            units.append(unit)
            units.sort()
            self._save_units()
        await self._safe_answer(
            call,
            self.strings["added"].format(unit=unit),
            show_alert=False,
        )
        await self._refresh_main(call)

    async def _delete_menu(self, call: InlineCall):
        await self._safe_answer(call)
        units = self._units_list()
        rows = []
        for unit in units:
            rows.append([self._button(unit, self._remove_unit, (unit,), "danger")])
        rows.append([self._button("Back", self._back_to_main, (), "primary")])
        rows.append([{"text": "Close", "action": "close"}])
        await call.edit("<b>Del unit</b>\n\nВыбери юнит для удаления из списка.", reply_markup=rows)

    async def _remove_unit(self, call: InlineCall, unit: str):
        unit = self._normalize_unit_name(unit)
        units = self._units_list()
        if unit in units:
            units.remove(unit)
            self._save_units()
            await self._safe_answer(
                call,
                self.strings["removed"].format(unit=unit),
                show_alert=False,
            )
        await self._refresh_main(call)

    async def _back_to_main(self, call: InlineCall):
        await self._safe_answer(call)
        await self._refresh_main(call)

    @loader.command(alias="sd", ru_doc="инлайн-меню управления systemd юнитами")
    async def systemd(self, message: Message):
        """Open inline systemd unit manager."""
        await self.inline.form(
            text=await self._main_text(),
            message=message,
            reply_markup=self._main_markup(),
        )
