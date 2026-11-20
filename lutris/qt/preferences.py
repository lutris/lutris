"""Expose the application's preferences to Qt Quick."""

from gettext import gettext as _
from typing import Any

from PySide6.QtCore import Property, QObject, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication

from lutris import settings
from lutris.backend import preferences
from lutris.backend.models import SourceSetting, SteamAccount, StoragePaths, SystemInfoSection
from lutris.qt.delegates import PromptController
from lutris.qt.tasks import start_task


class PreferencesController(QObject):
    requested = Signal()
    issueReportRequested = Signal()
    interfaceChanged = Signal()
    stateChanged = Signal()
    # The library shows other sources and views after these change
    sourcesChanged = Signal()

    def __init__(self, prompts: PromptController, parent: QObject) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._sources: tuple[SourceSetting, ...] = ()
        self._storage: StoragePaths | None = None
        self._accounts: tuple[SteamAccount, ...] = ()
        self._system_info: tuple[SystemInfoSection, ...] = ()
        self._tray_available = False
        self.apply_theme()

    def apply_theme(self) -> None:
        schemes = {"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}
        QGuiApplication.styleHints().setColorScheme(schemes.get(self._get_theme(), Qt.ColorScheme.Unknown))

    def _get_theme(self) -> str:
        return settings.read_setting("preferred_theme", "default")

    @Property(str, notify=interfaceChanged)
    def theme(self) -> str:
        return self._get_theme()

    def should_show_tray(self) -> bool:
        return self._tray_available and settings.read_bool_setting("show_tray_icon")

    @Property(bool, notify=interfaceChanged)
    def trayEnabled(self) -> bool:  # noqa: N802
        return settings.read_bool_setting("show_tray_icon")

    @Property(bool, notify=interfaceChanged)
    def trayAvailable(self) -> bool:  # noqa: N802
        return self._tray_available

    def set_tray_available(self, available: bool) -> None:
        self._tray_available = available
        self.interfaceChanged.emit()

    @Property(bool, notify=interfaceChanged)
    def hideBadges(self) -> bool:  # noqa: N802
        return settings.read_bool_setting("hide_badges_on_icons")

    @Property(bool, notify=interfaceChanged)
    def hideGameTitles(self) -> bool:  # noqa: N802
        return settings.read_bool_setting("hide_text_under_icons")

    @Property(bool, notify=interfaceChanged)
    def discordPresence(self) -> bool:  # noqa: N802
        return settings.read_bool_setting("discord_rpc")

    @Property(bool, notify=interfaceChanged)
    def minimizeOnLaunch(self) -> bool:  # noqa: N802
        return settings.read_bool_setting("hide_client_on_game_start")

    @Slot(str)
    def set_theme(self, theme: str) -> None:
        if theme in {"default", "light", "dark"}:
            settings.write_setting("preferred_theme", theme)
            self.apply_theme()
            self.interfaceChanged.emit()

    @Slot(str, bool)
    def set_interface_option(self, option: str, enabled: bool) -> None:
        if option in {
            "show_tray_icon",
            "hide_badges_on_icons",
            "hide_text_under_icons",
            "discord_rpc",
            "hide_client_on_game_start",
        }:
            settings.write_setting(option, enabled)
            self.interfaceChanged.emit()

    @Slot()
    def open_issue_report(self) -> None:
        self.issueReportRequested.emit()

    @Slot(QUrl, str)
    def save_issue_report(self, url: QUrl, description: str) -> None:
        start_task(self._save_issue_report(url.toLocalFile(), description), self._prompts.error)

    async def _save_issue_report(self, filename: str, description: str) -> None:
        await preferences.save_issue_report(filename, description)
        self._prompts.notice(_("Issue report saved to %s") % filename, rich=False)

    @Property(list, notify=stateChanged)
    def sources(self) -> list[dict[str, Any]]:
        return [
            {
                "id": source.id,
                "name": source.name,
                "description": source.description,
                "enabled": source.enabled,
                "inGamesView": source.in_games_view,
            }
            for source in self._sources
        ]

    @Property(dict, notify=stateChanged)
    def storage(self) -> dict[str, Any]:
        paths = self._storage
        if not paths:
            return {}
        return {
            "gamePath": paths.game_path,
            "cachePath": paths.installer_cache_path,
            "cacheMessage": paths.installer_cache_message,
            "cacheValid": paths.installer_cache_valid,
            "biosPath": paths.bios_path,
            "biosWarning": paths.bios_warning,
        }

    @Property(list, notify=stateChanged)
    def steamAccounts(self) -> list[dict[str, Any]]:  # noqa: N802
        return [{"id": account.id, "name": account.name, "active": account.active} for account in self._accounts]

    @Property(list, notify=stateChanged)
    def systemInfo(self) -> list[dict[str, Any]]:  # noqa: N802
        return [
            {"title": section.title, "items": [{"name": name, "value": value} for name, value in section.items]}
            for section in self._system_info
        ]

    @Slot()
    def open_preferences(self) -> None:
        self.requested.emit()
        start_task(self._load(), self._prompts.error)

    async def _load(self) -> None:
        self._sources = await preferences.list_sources()
        self._storage = await preferences.get_storage_paths()
        self._accounts = await preferences.list_steam_accounts()
        self.stateChanged.emit()
        self._system_info = await preferences.get_system_info()
        self.stateChanged.emit()

    @Slot(str, bool)
    def set_source_enabled(self, source_id: str, enabled: bool) -> None:
        start_task(self._change_source(preferences.set_source_enabled(source_id, enabled)), self._prompts.error)

    @Slot(str, bool)
    def set_source_in_games_view(self, source_id: str, shown: bool) -> None:
        start_task(self._change_source(preferences.set_source_in_games_view(source_id, shown)), self._prompts.error)

    async def _change_source(self, change: Any) -> None:
        await change
        self._sources = await preferences.list_sources()
        self.stateChanged.emit()
        self.sourcesChanged.emit()

    @Slot(QUrl, result=str)
    def local_path(self, url: QUrl) -> str:
        return url.toLocalFile()

    @Slot(str)
    def set_game_path(self, path: str) -> None:
        start_task(self._change_storage(preferences.set_game_path(path)), self._prompts.error)

    @Slot(str)
    def set_cache_path(self, path: str) -> None:
        start_task(self._change_storage(preferences.set_installer_cache_path(path)), self._prompts.error)

    @Slot(str)
    def set_bios_path(self, path: str) -> None:
        start_task(self._change_storage(preferences.set_bios_path(path)), self._prompts.error)

    async def _change_storage(self, change: Any) -> None:
        self._storage = await change
        self.stateChanged.emit()

    @Slot(str)
    def set_steam_account(self, account_id: str) -> None:
        start_task(self._set_steam_account(account_id), self._prompts.error)

    async def _set_steam_account(self, account_id: str) -> None:
        await preferences.set_steam_account(account_id)
        self._accounts = await preferences.list_steam_accounts()
        self.stateChanged.emit()

    @Slot()
    def copy_system_info(self) -> None:
        QGuiApplication.clipboard().setText(preferences.system_info_text(self._system_info))

    @Slot()
    def copy_log(self) -> None:
        start_task(self._copy_log(), self._prompts.error)

    async def _copy_log(self) -> None:
        QGuiApplication.clipboard().setText((await preferences.get_log()).strip())
