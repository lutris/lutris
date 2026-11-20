"""What the Qt frontend answers when the backend needs the user."""

from gettext import gettext as _
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QInputDialog, QLineEdit, QMessageBox, QWidget

from lutris.delegates import LaunchUIDelegate


class QtLaunchUIDelegate(LaunchUIDelegate):
    """Asks the user with Qt dialogs, over a parent window. The delegate's questions
    want their answers at once, so these dialogs are modal, and asyncio waits while
    they're open."""

    def __init__(self, parent: QWidget) -> None:
        self.parent = parent

    def _message_box(self, icon: QMessageBox.Icon, title: str, text: str) -> QMessageBox:
        box = QMessageBox(icon, title, text, QMessageBox.StandardButton.NoButton, self.parent)
        # Messages are Pango markup, which is close enough to Qt's rich text
        box.setTextFormat(Qt.TextFormat.RichText)
        return box

    def show_notice(self, message_markup: str, secondary: str | None = None) -> None:
        box = self._message_box(QMessageBox.Icon.Information, "Lutris", message_markup)
        if secondary:
            box.setInformativeText(secondary)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def ask_question(self, title: str, question_markup: str) -> bool:
        box = self._message_box(QMessageBox.Icon.Question, title, question_markup)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes

    def ask_for_text(self, title: str, question_markup: str, initial_value: str = "") -> str | None:
        text, accepted = QInputDialog.getText(
            self.parent, title, question_markup, QLineEdit.EchoMode.Normal, initial_value
        )
        return text if accepted else None

    def ask_for_file(self, message: str, default_path: str | None = None) -> str | None:
        path, _filter = QFileDialog.getOpenFileName(self.parent, message, default_path or "")
        return path or None

    def start_installer(
        self,
        installers: list[dict[str, Any]],
        service: Any = None,
        appid: str | None = None,
        installation_kind: Any = None,
    ) -> None:
        self.show_notice(_("Installing games isn't available in the Qt version of Lutris yet."))
