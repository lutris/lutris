"""Keep native tray integration separate from the Qt Quick window."""

from collections.abc import Callable
from gettext import gettext as _

from PySide6.QtCore import QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from lutris import settings
from lutris.qt.preferences import PreferencesController


class TrayIcon(QObject):
    def __init__(
        self,
        preferences: PreferencesController,
        show_window: Callable[[], None],
        quit_application: Callable[[], None],
        set_held: Callable[[bool], None],
        parent: QObject,
    ) -> None:
        super().__init__(parent)
        self._preferences = preferences
        self._set_held = set_held
        self._menu = QMenu()
        self._menu.addAction(_("Show Lutris")).triggered.connect(lambda: show_window())
        self._menu.addAction(_("Quit Lutris")).triggered.connect(lambda: quit_application())
        icon = QIcon.fromTheme(settings.APPLICATION_ID, QIcon.fromTheme("applications-games"))
        self._icon = QSystemTrayIcon(icon, self)
        self._icon.setContextMenu(self._menu)
        self._icon.setToolTip(_("Lutris"))
        self._icon.activated.connect(
            lambda reason: show_window() if reason == QSystemTrayIcon.ActivationReason.Trigger else None
        )
        self._preferences.set_tray_available(self._icon.isSystemTrayAvailable())
        self._preferences.interfaceChanged.connect(self._update)
        self._update()

    def _update(self) -> None:
        enabled = self._preferences.should_show_tray()
        self._icon.setVisible(enabled)
        self._set_held(enabled)

    def shutdown(self) -> None:
        self._preferences.interfaceChanged.disconnect(self._update)
        self._icon.hide()
        self._set_held(False)
