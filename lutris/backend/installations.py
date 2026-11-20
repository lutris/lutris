"""Run an install script chosen from an installer catalog.

An installation moves through stages, and each change is announced with
INSTALLATION_CHANGED and a plain InstallationInfo snapshot. Where the script
needs the user (extras, files, a menu, a disc), the installation waits in that
stage until the frontend answers with one of the calls below. The interpreter
and its files stay in the backend; frontends only see ids and plain data.
"""

import asyncio
import html
import os
import re
import traceback
from collections.abc import Callable, Coroutine
from gettext import gettext as _
from typing import Any
from uuid import uuid4

from lutris import settings
from lutris.backend import events, games, installers, shortcuts
from lutris.backend.models import (
    InstallationInfo,
    InstallerExtraInfo,
    InstallerFileInfo,
    InstallerMenuOption,
)
from lutris.config import LutrisConfig
from lutris.database import games as games_db
from lutris.delegates import InstallUIDelegate
from lutris.exceptions import LutrisError
from lutris.installer.errors import ScriptingError
from lutris.installer.installer_file import InstallerFile
from lutris.installer.installer_file_collection import InstallerFileCollection
from lutris.installer.interpreter import ScriptInterpreter
from lutris.runners import NonInstallableRunnerError, RunnerInstallationError
from lutris.util import system
from lutris.util.downloader import SimpleDownloader
from lutris.util.file_downloads import DownloadState, DownloadStatus, FileDownload
from lutris.util.log import logger
from lutris.util.log_buffer import LogBuffer
from lutris.util.notifications import NotificationRegistration, NotificationSource
from lutris.util.strings import human_size

# Fired with an InstallationInfo whenever an installation changes
INSTALLATION_CHANGED = NotificationSource()
# Fired with an installation's id when its command output changes
INSTALLATION_LOG_CHANGED = NotificationSource()

# How many of an installation's files download at the same time
MAX_DOWNLOADS = 3
# The shortcuts an installation can create once it finishes
SHORTCUT_KINDS = ("desktop", "menu")

type InstallerFileType = InstallerFile | InstallerFileCollection

_ACTIVE_STAGES = {"preparing", "extras", "files", "downloading", "installing", "menu", "disc", "cancelling"}


def _plain(markup: str) -> str:
    """Return the text of a Pango markup string."""
    return html.unescape(re.sub(r"<[^>]+>", "", markup or "")).strip()


class _RunnerDelegate(InstallUIDelegate):
    """Downloads runners from a worker thread, reporting progress to the installation."""

    def __init__(self, installation: "_Installation") -> None:
        self._installation = installation

    def download_install_file(self, url: str, destination: str) -> bool:
        downloader = SimpleDownloader(url, destination, overwrite=True)
        self._installation.on_thread(lambda: self._installation.set_runner_download(downloader))
        downloader.start()
        result = downloader.join()
        self._installation.on_thread(lambda: self._installation.set_runner_download(None))
        return result


class _MenuAnswer:
    """What the interpreter's input menu callback expects of the widget it was given."""

    def __init__(self, option_id: str) -> None:
        self._option_id = option_id

    def get_active_id(self) -> str:
        return self._option_id


class _InterpreterDelegate(ScriptInterpreter.InterpreterUIDelegate):
    """Turns the interpreter's calls, from any thread, into installation changes. The
    interpreter is built before its installation, which attaches itself afterwards."""

    _installation: "_Installation"

    def attach(self, installation: "_Installation") -> None:
        self._installation = installation

    def report_error(self, error: BaseException) -> None:
        self._installation.on_thread(lambda: self._installation.fail(error))

    def report_status(self, status: str) -> None:
        self._installation.on_thread(lambda: self._installation.set_status(status))

    def report_progress(self, fraction: float | None, text: str = "") -> None:
        self._installation.on_thread(lambda: self._installation.set_progress(fraction, text))

    def attach_log(self, command: Any) -> None:
        # Attached at once, so no output is missed
        command.set_log_buffer(self._installation.log)
        self._installation.on_thread(self._installation.show_log)

    def begin_input_menu(self, alias: str | None, options: list[dict[str, str]], preselect: str, callback: Any) -> None:
        self._installation.on_thread(lambda: self._installation.ask_menu(alias, options, preselect, callback))

    def begin_disc_prompt(self, message: str, requires: str, installer: Any, callback: Any) -> None:
        can_eject = installer.runner == "wine"
        self._installation.on_thread(lambda: self._installation.ask_disc(message, requires, can_eject, callback))

    def report_finished(self, game_id: str, status: str) -> None:
        self._installation.on_thread(lambda: self._installation.finish(game_id, status))


class _FileEntry:
    """One of the files an installation needs, with the source the user picked."""

    def __init__(self, file: InstallerFileType) -> None:
        self.file = file
        self.provider = file.default_provider
        self.user_path = ""
        self.cache = file.uses_pga_cache()
        self.state = "pending"
        self.status = DownloadStatus()
        self.error = ""
        self.download: FileDownload | None = None
        self.registration: NotificationRegistration | None = None

    @property
    def providers(self) -> tuple[str, ...]:
        found = self.file.providers
        if not (isinstance(self.file, InstallerFileCollection) and self.file.service == "amazon"):
            found = found | {"user"}
        return tuple(provider for provider in ("download", "pga", "user") if provider in found)

    @property
    def ready(self) -> bool:
        if self.provider == "user" and not self.user_path:
            return False
        return self.provider in self.providers and self.file.is_ready(self.provider)

    def info(self) -> InstallerFileInfo:
        status = self.status
        progress = ""
        if self.state == "downloading" and status.full_size:
            progress = _("{downloaded} / {size}, {time} remaining").format(
                downloaded=human_size(status.downloaded_size), size=human_size(status.full_size), time=status.time_left
            )
        return InstallerFileInfo(
            id=self.file.id,
            label=_plain(self.file.get_label()),
            hint=_plain(self.file.human_url),
            details=self.file.auxiliary_info or "",
            providers=self.providers,
            provider=self.provider,
            user_path=self.user_path,
            ready=self.ready,
            state=self.state,
            fraction=status.fraction,
            progress_text=progress,
            error=self.error,
        )


class _Installation:
    """An installation's state; its methods run on the main loop unless noted."""

    def __init__(
        self,
        interpreter: ScriptInterpreter,
        delegate: _InterpreterDelegate,
        directory: str,
        shortcut_kinds: tuple[str, ...],
    ) -> None:
        self.id = uuid4().hex
        self.loop = asyncio.get_running_loop()
        self.log = LogBuffer()
        self._log_registration = self.log.changed.register(lambda *_args: INSTALLATION_LOG_CHANGED.fire(self.id))
        self.interpreter = interpreter
        delegate.attach(self)
        if self.interpreter.installer.creates_game_folder and directory:
            self.interpreter.target_path = os.path.expanduser(directory)
        self.shortcut_kinds = shortcut_kinds
        self.stage = "preparing"
        self.status = _("Preparing Lutris for installation")
        self.progress: float | None = -1.0
        self.progress_text = ""
        self.extras: dict[str, dict[str, Any]] = {}
        self.extra_sources: dict[str, str] = {}
        self.files: dict[str, _FileEntry] = {}
        self.menu: tuple[str | None, tuple[InstallerMenuOption, ...], str, Any] | None = None
        self.disc: tuple[str, bool, Any] | None = None
        self.has_log = False
        self.commands_started = False
        self.game_id = ""
        self.error_details = ""
        self.runner_download: SimpleDownloader | None = None
        # Set when the frontend closed it while it was being reverted
        self.closing = False
        self.tasks: set[asyncio.Task[None]] = set()

    @property
    def active(self) -> bool:
        return self.stage in _ACTIVE_STAGES

    def info(self) -> InstallationInfo:
        menu_options: tuple[InstallerMenuOption, ...] = ()
        preselect = ""
        if self.menu:
            _alias, menu_options, preselect, _callback = self.menu
        return InstallationInfo(
            id=self.id,
            game_name=self.interpreter.installer.game_name,
            stage=self.stage,
            running=self.active,
            status=self.status,
            progress=self.progress,
            progress_text=self.progress_text,
            extras=tuple(
                InstallerExtraInfo(id=extra_id, source=self.extra_sources[extra_id], label=_extra_label(extra))
                for extra_id, extra in self.extras.items()
            ),
            files=tuple(entry.info() for entry in self.files.values()),
            menu_options=menu_options,
            menu_preselect=preselect,
            disc_requires=self.disc[0] if self.disc else "",
            disc_can_eject=bool(self.disc and self.disc[1]),
            has_log=self.has_log,
            can_remove_files=self._can_remove_files(),
            game_id=self.game_id,
            error_details=self.error_details,
        )

    def changed(self) -> None:
        INSTALLATION_CHANGED.fire(self.info())

    def on_thread(self, update: Callable[[], None]) -> None:
        """Run an update on the main loop; callable from any thread."""

        def run() -> None:
            try:
                update()
            except Exception as error:
                logger.exception("Installation update failed")
                self.fail(error)

        self.loop.call_soon_threadsafe(run)

    def _can_remove_files(self) -> bool:
        target = self.interpreter.target_path
        return bool(
            target and self.interpreter.game_dir_created and system.is_removeable(target, LutrisConfig().system_config)
        )

    # Progress reported by the interpreter

    def set_status(self, status: str) -> None:
        if self.active:
            self.status = _plain(status)
            self.changed()

    def set_progress(self, fraction: float | None, text: str = "") -> None:
        if self.active:
            self.progress = fraction
            self.progress_text = text
            self.changed()

    def set_runner_download(self, downloader: SimpleDownloader | None) -> None:
        self.runner_download = downloader

    def show_log(self) -> None:
        if not self.has_log:
            self.has_log = True
            self.changed()

    def fail(self, error: BaseException) -> None:
        if not self.active:
            return
        logger.error("Installation of %s failed: %s", self.interpreter.installer.game_name, error)
        self._stop_downloads()
        self.stage = "failed"
        self.status = error.message if isinstance(error, LutrisError) else str(error)
        self.progress = None
        if not getattr(error, "is_expected", False):
            self.error_details = "".join(traceback.format_exception(error)).strip()
        self.changed()

    # The stages, in order

    async def prepare(self) -> None:
        interpreter = self.interpreter
        runners = await asyncio.to_thread(interpreter.get_runners_to_install)
        for runner in runners:
            self.set_status(_("Installing %s") % runner.human_name)
            version = runner.get_installer_runner_version(interpreter.installer)
            try:
                await asyncio.to_thread(runner.install, _RunnerDelegate(self), version=version)
            except (NonInstallableRunnerError, RunnerInstallationError) as error:
                raise ScriptingError.wrap(error) from error
            if not self.active:
                return
            if not runner.is_installed_for(interpreter):
                raise ScriptingError(_("%s was not installed.") % runner.human_name)

        self.set_status(_("Looking for extra content"))
        all_extras = await asyncio.to_thread(interpreter.get_extras)
        if not self.active:
            return
        if all_extras:
            for source, extras in all_extras.items():
                for extra in extras:
                    extra_id = str(len(self.extras))
                    self.extras[extra_id] = extra
                    self.extra_sources[extra_id] = source
            self._enter(
                "extras",
                _("This game has extra content. The extras you select go into the game's 'extras' folder."),
            )
            return
        await self.prepare_files([])

    async def prepare_files(self, extras: list[dict[str, Any]]) -> None:
        self._enter("preparing", _("Preparing game files"), progress=-1.0)
        installer = self.interpreter.installer
        await asyncio.to_thread(installer.prepare_game_files, extras)
        if not self.active:
            return
        if not installer.files:
            self.launch_commands()
            return
        for file in installer.files:
            if file.default_provider == "steam":
                raise ScriptingError(_("Files from Steam can't be installed from the Qt frontend yet."))
            self.files[file.id] = _FileEntry(file)
        self._enter("files", _("Review the files needed for the installation, then start it."))

    def set_file_source(self, file_id: str, provider: str, path: str) -> None:
        self._require_stage("files")
        entry = self._file(file_id)
        if provider not in entry.providers:
            raise LutrisError(_("This file can't come from there."))
        entry.provider = provider
        if provider == "user":
            entry.user_path = os.path.expanduser(path.strip()) if path.strip() else ""
            if entry.user_path:
                entry.file.override_dest_file(entry.user_path)
        self.changed()

    def start_files(self) -> None:
        self._require_stage("files")
        not_ready = [entry.file.id for entry in self.files.values() if not entry.ready]
        if not_ready:
            raise LutrisError(_("Choose where each file comes from before installing."))
        self._enter("downloading", _("Downloading game data"), progress=None)
        for entry in self.files.values():
            if entry.provider == "download":
                continue
            entry.file.prepare()
            entry.state = "available"
            if entry.cache:
                entry.file.save_to_cache()
        self._start_queued_downloads()
        self._check_files_available()

    def retry_file(self, file_id: str) -> None:
        self._require_stage("downloading")
        entry = self._file(file_id)
        if entry.state in ("failed", "cancelled") and entry.download:
            entry.state = "downloading"
            entry.error = ""
            entry.download.retry()
            self.changed()

    def _start_queued_downloads(self) -> None:
        downloading = sum(1 for entry in self.files.values() if entry.state == "downloading")
        for entry in self.files.values():
            if downloading >= MAX_DOWNLOADS:
                break
            if entry.provider == "download" and entry.state == "pending":
                entry.file.prepare()
                entry.file.remove_previous()
                entry.download = entry.file.create_download()
                entry.registration = entry.download.changed.register(
                    lambda state, status, error, entry=entry: self._on_download_changed(entry, state, status, error)
                )
                entry.state = "downloading"
                downloading += 1
                entry.download.start()

    def _on_download_changed(
        self, entry: _FileEntry, state: DownloadState, status: DownloadStatus, error: BaseException | None
    ) -> None:
        if self.stage != "downloading":
            return
        entry.status = status
        if state == DownloadState.COMPLETED:
            try:
                entry.file.check_hash()
            except ScriptingError as hash_error:
                entry.state = "failed"
                entry.error = str(hash_error)
            else:
                entry.state = "available"
                if entry.cache:
                    entry.file.save_to_cache()
        elif state == DownloadState.FAILED:
            entry.state = "failed"
            entry.error = str(error or _("The download failed."))
        elif state == DownloadState.CANCELLED:
            entry.state = "cancelled"
            entry.error = str(error) if error else _("Download interrupted")
        if state != DownloadState.DOWNLOADING:
            self._start_queued_downloads()
        self.changed()
        self._check_files_available()

    def _check_files_available(self) -> None:
        if self.stage == "downloading" and all(entry.state == "available" for entry in self.files.values()):
            game_files: dict[str, str] = {}
            for entry in self.files.values():
                game_files.update(entry.file.get_dest_files_by_id())
            self.interpreter.game_files = game_files
            self.launch_commands()

    def launch_commands(self) -> None:
        logger.info("Launching installer commands for %s", self.interpreter.installer.game_name)
        self.commands_started = True
        self._enter("installing", _("Installing game data"), progress=-1.0)
        self.interpreter.installer.install_extras()
        try:
            self.interpreter.launch_installer_commands()
        except Exception as error:
            self.fail(error)

    def ask_menu(self, alias: str | None, options: list[dict[str, str]], preselect: str, callback: Any) -> None:
        if not self.active:
            return
        choices = tuple(
            InstallerMenuOption(id=str(key), label=str(label)) for option in options for key, label in option.items()
        )
        self.menu = (alias, choices, preselect, callback)
        self._enter("menu", self.status or _("Choose an option"))

    def answer_menu(self, option_id: str) -> None:
        self._require_stage("menu")
        assert self.menu is not None
        alias, choices, _preselect, callback = self.menu
        if option_id not in {choice.id for choice in choices}:
            raise LutrisError(_("Choose one of the options."))
        self.menu = None
        self._enter("installing", self.status, progress=-1.0)
        try:
            callback(alias, _MenuAnswer(option_id))
        except Exception as error:
            self.fail(error)

    def ask_disc(self, message: str, requires: str, can_eject: bool, callback: Any) -> None:
        if not self.active:
            return
        self.disc = (requires, can_eject, callback)
        self._enter("disc", _plain(message))

    def answer_disc(self, path: str) -> None:
        self._require_stage("disc")
        assert self.disc is not None
        requires, _can_eject, callback = self.disc
        try:
            callback(None, requires, path or None)
        except RuntimeError as error:
            self.status = str(error)
            self.changed()
            return
        self.disc = None
        if self.stage == "disc":
            self._enter("installing", _("Installing game data"), progress=-1.0)

    def eject_disc(self) -> None:
        self._require_stage("disc")
        self.interpreter.eject_wine_disc()

    def finish(self, game_id: str, status: str) -> None:
        if not self.active:
            return
        self.game_id = str(game_id or "")
        self.stage = "finished"
        self.status = _plain(status)
        self.progress = None
        self.progress_text = ""
        self.changed()
        if self.game_id:
            self.start(self._announce_installed())

    def start(self, operation: Coroutine[Any, Any, None]) -> None:
        """Run part of the installation on the main loop, failing it on any error."""

        async def run() -> None:
            try:
                await operation
            except Exception as error:
                self.fail(error)

        task = self.loop.create_task(run())
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _announce_installed(self) -> None:
        for kind in self.shortcut_kinds:
            try:
                await shortcuts.set_shortcut(self.game_id, kind, True)
            except LutrisError as error:
                logger.warning("Could not create the %s shortcut: %s", kind, error)
        if row := games_db.get_game_by_field(self.game_id, "id"):
            events.GAME_INSTALLED.fire(games.to_game_info(row))

    def cancel(self, remove_files: bool) -> None:
        if not self.active or self.stage == "cancelling":
            return
        self._stop_downloads()
        if self.runner_download:
            self.runner_download.cancel()
        if not self.commands_started:
            self._enter("cancelled", _("The installation was cancelled."), progress=None)
            return
        self._enter("cancelling", _("Cancelling installation…"), progress=-1.0)

        def on_reverted() -> None:
            self.stage = "cancelled"
            self.status = _("The installation was cancelled.")
            self.progress = None
            self.changed()

        def on_error(error: BaseException) -> None:
            self.stage = "failed"
            self.status = str(error)
            self.progress = None
            self.changed()

        self.interpreter.revert(
            remove_game_dir=remove_files and self._can_remove_files(),
            completion_function=lambda: self.on_thread(on_reverted),
            error_function=lambda error: self.on_thread(lambda: on_error(error)),
        )

    def close(self) -> None:
        self._stop_downloads()
        self._log_registration.unregister()
        try:
            self.interpreter.cleanup()
        except OSError as error:
            logger.warning("Could not clean up the installer cache: %s", error)

    def _stop_downloads(self) -> None:
        for entry in self.files.values():
            if entry.download and entry.state == "downloading":
                entry.download.cancel()
            if entry.registration:
                entry.registration.unregister()
                entry.registration = None

    def _enter(self, stage: str, status: str, progress: float | None = None) -> None:
        self.stage = stage
        self.status = status
        self.progress = progress
        self.progress_text = ""
        self.changed()

    def _require_stage(self, stage: str) -> None:
        if self.stage != stage:
            raise LutrisError(_("The installation isn't waiting for that anymore."))

    def _file(self, file_id: str) -> _FileEntry:
        try:
            return self.files[file_id]
        except KeyError as error:
            raise LutrisError(_("The installation doesn't need that file.")) from error


def _extra_label(extra: dict[str, Any]) -> str:
    details = []
    if extra.get("total_size"):
        details.append(human_size(extra["total_size"]))
    if extra.get("type"):
        details.append(extra["type"])
    label = str(extra.get("name") or "")
    return f"{label} ({', '.join(details)})" if details else label


_installations: dict[str, _Installation] = {}


def _get(installation_id: str) -> _Installation:
    try:
        return _installations[installation_id]
    except KeyError as error:
        raise LutrisError(_("This installation is no longer running.")) from error


async def start_installation(
    catalog_id: str, choice_id: str, directory: str = "", shortcut_kinds: tuple[str, ...] = ()
) -> InstallationInfo:
    """Start installing with a catalog's script into a folder, if the script creates one.

    The installation runs on: follow INSTALLATION_CHANGED for its progress and the
    questions it asks, and call close_installation once it's over."""
    unknown = set(shortcut_kinds) - set(SHORTCUT_KINDS)
    if unknown:
        raise LutrisError(_("Unknown shortcut destinations: %s") % ", ".join(sorted(unknown)))
    script = installers.copy_script(catalog_id, choice_id)
    delegate = _InterpreterDelegate()
    interpreter = await asyncio.to_thread(ScriptInterpreter, script, delegate)
    installation = _Installation(interpreter, delegate, directory, shortcut_kinds)
    _installations[installation.id] = installation
    installation.start(installation.prepare())
    return installation.info()


async def get_installation(installation_id: str) -> InstallationInfo:
    return _get(installation_id).info()


async def get_installation_log(installation_id: str) -> str:
    """Return the output the installer's commands have written."""
    return _get(installation_id).log.text


async def choose_extras(installation_id: str, extra_ids: list[str]) -> None:
    """Pick the extras to install, which may be none, and go on to the game's files."""
    installation = _get(installation_id)
    installation._require_stage("extras")
    unknown = set(extra_ids) - set(installation.extras)
    if unknown:
        raise LutrisError(_("Some of these extras aren't offered for this game."))
    installation.start(installation.prepare_files([installation.extras[extra_id] for extra_id in extra_ids]))


async def set_file_source(installation_id: str, file_id: str, provider: str, path: str = "") -> None:
    """Choose where a file comes from: "download", "pga" (the cache) or "user", with its path."""
    _get(installation_id).set_file_source(file_id, provider, path)


async def start_files(installation_id: str) -> None:
    """Fetch the files and, once they're all available, run the script's commands."""
    _get(installation_id).start_files()


async def retry_file(installation_id: str, file_id: str) -> None:
    _get(installation_id).retry_file(file_id)


async def answer_menu(installation_id: str, option_id: str) -> None:
    _get(installation_id).answer_menu(option_id)


async def answer_disc(installation_id: str, path: str = "") -> None:
    """Continue with a disc mounted at a path; without one, look through the mounted discs."""
    _get(installation_id).answer_disc(path)


async def eject_disc(installation_id: str) -> None:
    await asyncio.to_thread(_get(installation_id).eject_disc)


async def cancel_installation(installation_id: str, remove_files: bool = True) -> None:
    """Stop an installation, removing the folder it created if asked and allowed."""
    _get(installation_id).cancel(remove_files)


async def close_installation(installation_id: str) -> None:
    """Forget an installation that is over, cancelling it first if it isn't."""
    installation = _installations.get(installation_id)
    if not installation:
        return
    if installation.active:
        installation.cancel(remove_files=True)
    if installation.stage == "cancelling":
        installation.closing = True
        return
    del _installations[installation_id]
    installation.close()


def _forget_when_reverted(info: InstallationInfo) -> None:
    installation = _installations.get(info.id)
    if installation and installation.closing and not installation.active:
        del _installations[info.id]
        installation.close()


INSTALLATION_CHANGED.register(_forget_when_reverted)

_SHORTCUT_SETTINGS = {kind: f"installer_create_{kind}_shortcut" for kind in SHORTCUT_KINDS}


async def get_default_shortcuts() -> tuple[str, ...]:
    """Return the shortcut destinations last chosen for an installation."""
    return tuple(kind for kind, key in _SHORTCUT_SETTINGS.items() if settings.read_bool_setting(key, False))


async def set_default_shortcuts(kinds: tuple[str, ...]) -> None:
    for kind, key in _SHORTCUT_SETTINGS.items():
        settings.write_setting(key, kind in kinds)
