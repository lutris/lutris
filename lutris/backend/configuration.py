"""Edit the options of a game, a runner or the whole system, as plain data.

Opening a configuration returns a ConfigForm: every option the level offers,
evaluated against the configuration being edited, including the option
dicts' callables (visibility, conditions, choices, warnings). The backend keeps
the configuration under the form's id; set_option and reset_option change it
and return the form evaluated again, and save_config writes it out. Nothing is
written until then.
"""

import asyncio
import html
import re
from collections import OrderedDict
from collections.abc import Callable, Mapping
from gettext import gettext as _
from inspect import Parameter, signature
from typing import Any
from uuid import uuid4

from lutris import settings, sysoptions
from lutris.backend import events, games
from lutris.backend.models import ConfigChoice, ConfigForm, ConfigOptionInfo, ConfigPage
from lutris.config import LutrisConfig
from lutris.database import games as games_db
from lutris.exceptions import LutrisError
from lutris.runners import InvalidRunnerError, import_runner
from lutris.util.log import logger
from lutris.util.notifications import NotificationSource
from lutris.util.wine.wine import clear_wine_version_cache

# Fired with a form's id when its options change on their own, such as choices that
# finished loading in the background; get_config_form returns the new state
CONFIG_FORM_CHANGED = NotificationSource()

# How many forms are kept for frontends that never close theirs
_FORM_LIMIT = 8
_SECTION_TITLES = {"game": _("Game options"), "runner": _("Runner options"), "system": _("System options")}
_SHOW_ADVANCED_SETTING = "show_advanced_options"

type Option = dict[str, Any]


def _plain(markup: object) -> str:
    """Return the text of a Pango markup string."""
    if not markup:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", str(markup))).strip()


def _to_bool(value: object) -> bool | None:
    """Read a bool the way the GTK switches do, so the string 'False' isn't true."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.casefold().strip()
        return True if text == "true" else False if text == "false" else None
    return bool(value)


class _Form:
    """A configuration being edited; evaluated in worker threads, one call at a time."""

    def __init__(self, level: str, title: str, config: LutrisConfig, game_id: str = "") -> None:
        self.id = uuid4().hex
        self.level = level
        self.title = title
        self.config = config
        self.game_id = game_id
        self.lock = asyncio.Lock()
        self.runner = None
        if config.runner_slug:
            try:
                self.runner = import_runner(config.runner_slug)()
            except InvalidRunnerError:
                logger.warning("Unknown runner %s", config.runner_slug)
        self.sections = [section for section in ("game", "runner", "system") if self._has_section(section)]

    def _has_section(self, section: str) -> bool:
        if section == "game":
            return self.level == "game" and self.runner is not None
        if section == "runner":
            return self.level in ("game", "runner") and self.runner is not None
        return True

    def options(self, section: str) -> list[Option]:
        if section == "game":
            return list(self.runner.game_options) if self.runner else []
        if section == "runner":
            return list(self.runner.get_runner_options()) if self.runner else []
        if self.config.runner_slug:
            return sysoptions.with_runner_overrides(self.config.runner_slug)
        return sysoptions.system_options

    def find(self, section: str, key: str) -> Option:
        if section in self.sections:
            for option in self.options(section):
                if option["option"] == key and self._in_scope(option):
                    return option
        raise LutrisError(_("This configuration has no option '%s'.") % key)

    def cascaded(self, section: str) -> dict[str, Any]:
        return getattr(self.config, f"{section}_config")

    def raw(self, section: str) -> dict[str, Any]:
        return getattr(self.config, f"raw_{section}_config")

    def _in_scope(self, option: Option) -> bool:
        return "scope" not in option or self.level in option["scope"]

    # Evaluation

    def evaluate(self, value: Any, key: str) -> Any:
        """Call an option's callable attribute as the GTK widget generator does: with the
        option's key and the configuration, or as many of those as it takes."""
        if not callable(value):
            return value
        try:
            parameters = signature(value).parameters.values()
        except TypeError, ValueError:
            return value(key, self.config)
        count = len(parameters)
        if count >= 2 or any(parameter.kind == Parameter.VAR_POSITIONAL for parameter in parameters):
            return value(key, self.config)
        if count == 1:
            return value(key)
        return value()

    def attribute(self, option: Option, name: str, default: Any) -> Any:
        if name not in option:
            return default
        try:
            return self.evaluate(option[name], option["option"])
        except Exception as error:
            logger.exception("Unable to evaluate '%s' of option '%s': %s", name, option["option"], error)
            return default

    def flag(self, option: Option, name: str) -> bool:
        value = self.attribute(option, name, True)
        return bool(value) if value is not None else True

    def default(self, option: Option) -> Any:
        return self.attribute(option, "default", None)

    def current(self, section: str, option: Option) -> Any:
        config = self.cascaded(section)
        key = option["option"]
        return config[key] if key in config else self.default(option)

    # Building the form

    def form(self) -> ConfigForm:
        return ConfigForm(
            id=self.id,
            level=self.level,
            title=self.title,
            pages=tuple(self.page(section) for section in self.sections),
            show_advanced=settings.read_setting(_SHOW_ADVANCED_SETTING) == "True",
        )

    def page(self, section: str) -> ConfigPage:
        if section == "runner" and self.level == "game":
            description = _("If modified, these options supersede the same options from the base runner configuration.")
        elif section == "system" and self.level == "game":
            description = _(
                "If modified, these options supersede the same options from the base runner configuration, "
                "which themselves supersede the global preferences."
            )
        elif section == "system" and self.level == "runner":
            description = _("If modified, these options supersede the same options from the global preferences.")
        else:
            description = ""
        options: list[ConfigOptionInfo] = []
        all_options = {option["option"]: option for option in self.options(section)}
        for option in all_options.values():
            if not self._in_scope(option):
                continue
            try:
                info = self.option_info(section, option, all_options)
            except Exception as error:
                logger.exception("Failed to evaluate option '%s': %s", option.get("option"), error)
                continue
            if info:
                options.append(info)
        return ConfigPage(
            section=section, title=_SECTION_TITLES[section], description=description, options=tuple(options)
        )

    def option_info(self, section: str, option: Option, all_options: dict[str, Option]) -> ConfigOptionInfo | None:
        if not self.flag(option, "available"):
            return None
        key = option["option"]
        option_type = option["type"]
        default = self.default(option)
        value = self.current(section, option)
        choices: tuple[ConfigChoice, ...] = ()
        default_label = default if isinstance(default, str) else ""
        warning = _plain(self.attribute(option, "warning", ""))
        error = _plain(self.attribute(option, "error", ""))

        if option_type == "bool":
            value = bool(_to_bool(value)) if _to_bool(value) is not None else bool(_to_bool(default))
            default = bool(_to_bool(default))
            default_label = _("Enabled") if default else _("Disabled")
        elif option_type == "range":
            value = _to_int(value, _to_int(default, int(option.get("min", 0))))
        elif option_type in ("choice", "choice_with_entry", "choice_with_search"):
            choices, label = self.choices(option, default)
            default_label = label or default_label
            value = "" if value is None else str(value)
            values = {choice.value for choice in choices}
            if value and value not in values:
                if option_type == "choice":
                    warning = warning or (
                        _("The setting '%s' is no longer available. You should select another choice.") % value
                    )
                choices = (ConfigChoice(label=value, value=value), *choices)
            elif not value and option_type == "choice" and default is not None:
                value = str(default)
        elif option_type == "multiple_file":
            value = [str(path) for path in value] if isinstance(value, (list, tuple)) else ([value] if value else [])
        elif option_type == "mapping":
            value = {str(name): str(text) for name, text in value.items()} if isinstance(value, Mapping) else {}
            default = dict(default) if isinstance(default, Mapping) else {}
        elif option_type != "label":
            value = "" if value is None else str(value)

        enabled = self.flag(option, "condition") and not error
        conditional_on = option.get("conditional_on")
        if conditional_on and conditional_on in all_options:
            if not self.current(section, all_options[conditional_on]):
                enabled = False

        cascaded_value = self.cascaded(section).get(key, default)
        return ConfigOptionInfo(
            section=section,
            key=key,
            type=option_type,
            label=_plain(option.get("label", key)),
            group=_plain(option.get("section", "")),
            help=_plain(option.get("help", "")),
            value=value,
            default=_plain_value(default),
            default_label=str(default_label or ""),
            choices=choices,
            minimum=_to_int(option.get("min"), None),
            maximum=_to_int(option.get("max"), None),
            advanced=bool(option.get("advanced")),
            visible=self.flag(option, "visible"),
            enabled=enabled,
            set_here=key in self.raw(section),
            changed_below=key not in self.raw(section) and cascaded_value != default,
            warning=warning,
            error=error,
        )

    def choices(self, option: Option, default: Any) -> tuple[tuple[ConfigChoice, ...], str]:
        source = option.get("choices")
        evaluated = self.attribute(option, "choices", [])
        if callable(source) and hasattr(source, "register_reload_callback") and not evaluated:
            # Choices that load in the background announce themselves when ready
            source.register_reload_callback(lambda: CONFIG_FORM_CHANGED.fire(self.id))
        pairs: list[tuple[Any, Any]]
        if isinstance(evaluated, Mapping):
            pairs = list(evaluated.items())
        elif evaluated and isinstance(evaluated, (list, tuple)) and isinstance(evaluated[0], str):
            pairs = [(choice, choice) for choice in evaluated]
        else:
            pairs = [
                tuple(choice) for choice in evaluated or () if isinstance(choice, (list, tuple)) and len(choice) == 2
            ]
        default_label = ""
        result = []
        for label, value in pairs:
            label = _plain(label)
            if value == default:
                default_label = label
                label = _("%s (default)") % label
            result.append(ConfigChoice(label=label, value="" if value is None else str(value)))
        return tuple(result), default_label

    # Changes

    def set(self, section: str, key: str, value: Any) -> None:
        option = self.find(section, key)
        self.raw(section)[key] = _checked_value(option, value)
        self.config.update_cascaded_config()

    def reset(self, section: str, key: str) -> None:
        self.find(section, key)
        self.raw(section).pop(key, None)
        self.config.update_cascaded_config()

    def save(self) -> None:
        invalid = []
        for section in ("game", "runner"):
            if section not in self.sections:
                continue
            values = self.cascaded(section)
            for option in self.options(section):
                validator = option.get("validator")
                if validator and option["option"] in values:
                    try:
                        validator(values[option["option"]])
                    except Exception:
                        invalid.append(_plain(option.get("label", option["option"])))
        if invalid:
            raise LutrisError(_("The following fields have invalid values: ") + ", ".join(invalid))
        self.config.save()


def _to_int(value: object, default: Any) -> Any:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _plain_value(value: object) -> object:
    """Return a value that's plain data, as JSON would carry it."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {str(name): _plain_value(item) for name, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_value(item) for item in value]
    return str(value)


def _checked_value(option: Option, value: Any) -> Any:
    """Return a value of the type an option stores, or raise LutrisError."""
    option_type = option["type"]
    label = _plain(option.get("label", option["option"]))
    if option_type == "label":
        raise LutrisError(_("'%s' can't be changed.") % label)
    if option_type == "bool":
        flag = _to_bool(value)
        if flag is None:
            raise LutrisError(_("'%s' must be on or off.") % label)
        return flag
    if option_type == "range":
        number = _to_int(value, None)
        minimum, maximum = _to_int(option.get("min"), None), _to_int(option.get("max"), None)
        if number is None or (minimum is not None and number < minimum) or (maximum is not None and number > maximum):
            raise LutrisError(_("'%s' must be a number from %s to %s.") % (label, minimum, maximum))
        return number
    if option_type == "multiple_file":
        if not isinstance(value, (list, tuple)):
            raise LutrisError(_("'%s' must be a list of files.") % label)
        return [str(path) for path in value if str(path)]
    if option_type == "mapping":
        if not isinstance(value, Mapping):
            raise LutrisError(_("'%s' must be a list of names and values.") % label)
        return {str(name).strip(): str(text) for name, text in value.items() if str(name).strip()}
    return "" if value is None else str(value)


_forms: OrderedDict[str, _Form] = OrderedDict()


def _get(form_id: str) -> _Form:
    try:
        form = _forms[form_id]
    except KeyError as error:
        raise LutrisError(_("This configuration was closed. Open it again.")) from error
    _forms.move_to_end(form_id)
    return form


async def _open(build: Callable[[], _Form]) -> ConfigForm:
    form = await asyncio.to_thread(build)
    _forms[form.id] = form
    while len(_forms) > _FORM_LIMIT:
        _forms.popitem(last=False)
    async with form.lock:
        return await asyncio.to_thread(form.form)


async def _change(form_id: str, change: Callable[[_Form], None]) -> ConfigForm:
    form = _get(form_id)
    async with form.lock:

        def apply() -> ConfigForm:
            change(form)
            return form.form()

        return await asyncio.to_thread(apply)


async def open_game_config(game_id: str) -> ConfigForm:
    """Open an installed game's options, with its runner's and the system's at game level."""
    row = games_db.get_game_by_field(game_id, "id")
    if row is None:
        raise LutrisError(_("This game is no longer in the library."))
    if not row.get("runner") or not row.get("configpath"):
        raise LutrisError(_("%s has no configuration yet. Install it first.") % row["name"])

    def build() -> _Form:
        clear_wine_version_cache()
        config = LutrisConfig(runner_slug=row["runner"], game_config_id=row["configpath"])
        return _Form("game", _("Configure %s") % row["name"], config, game_id=str(row["id"]))

    return await _open(build)


async def open_runner_config(runner_name: str) -> ConfigForm:
    """Open a runner's options, with the system's at runner level."""
    try:
        runner = import_runner(runner_name)()
    except InvalidRunnerError as error:
        raise LutrisError(_("There is no runner called '%s'.") % runner_name) from error

    def build() -> _Form:
        clear_wine_version_cache()
        return _Form("runner", _("Configure %s") % runner.human_name, LutrisConfig(runner_slug=runner_name))

    return await _open(build)


async def open_system_config() -> ConfigForm:
    """Open the global system options, which every runner and game starts from."""
    return await _open(lambda: _Form("system", _("Global options"), LutrisConfig()))


async def get_config_form(form_id: str) -> ConfigForm:
    form = _get(form_id)
    async with form.lock:
        return await asyncio.to_thread(form.form)


async def set_option(form_id: str, section: str, key: str, value: Any) -> ConfigForm:
    """Set an option at the form's level; nothing is written until save_config."""
    return await _change(form_id, lambda form: form.set(section, key, value))


async def reset_option(form_id: str, section: str, key: str) -> ConfigForm:
    """Stop setting an option at the form's level, so it comes from the level below."""
    return await _change(form_id, lambda form: form.reset(section, key))


async def save_config(form_id: str) -> None:
    """Write the form's configuration; the form stays open."""
    form = _get(form_id)
    async with form.lock:
        await asyncio.to_thread(form.save)
    if form.game_id and (row := games_db.get_game_by_field(form.game_id, "id")):
        events.GAME_CHANGED.fire(games.to_game_info(row))


async def close_config(form_id: str) -> None:
    """Forget a form, discarding unsaved changes."""
    _forms.pop(form_id, None)


async def set_show_advanced(show: bool) -> None:
    """Remember whether configuration forms should show advanced options."""
    settings.write_setting(_SHOW_ADVANCED_SETTING, show)
