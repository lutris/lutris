"""Bridge synchronous launch prompts to QML dialogs."""

from collections import deque
from gettext import gettext as _
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEventLoop, QObject, QUrl, Signal, Slot

from lutris.delegates import LaunchUIDelegate
from lutris.exceptions import LutrisError

type Notice = tuple[str, str, str, bool]


class PromptController(QObject):
    noticeRequested = Signal(str, str, str, bool)
    inputRequested = Signal(str, str, str, str)
    cancelRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._notices: deque[Notice] = deque()
        self._notice_open = False
        self._loop: QEventLoop | None = None
        self._answer: str | None = None
        self._answered = False

    def notice(self, message: str, secondary: str = "", *, title: str = "Lutris", rich: bool = True) -> None:
        self._notices.append((title, message, secondary, rich))
        if not self._notice_open:
            self.notice_finished()

    def error(self, error: BaseException) -> None:
        message = error.message if isinstance(error, LutrisError) else str(error)
        self.notice(message, title=_("Error"), rich=False)

    @Slot()
    def notice_finished(self) -> None:
        self._notice_open = bool(self._notices)
        if self._notice_open:
            self.noticeRequested.emit(*self._notices.popleft())

    def ask(self, kind: str, title: str, message: str, initial: str = "") -> str | None:
        if self._loop is not None:
            return None
        loop = QEventLoop()
        self._loop = loop
        self._answer = None
        self._answered = False
        try:
            self.inputRequested.emit(kind, title, message, initial)
            if not self._answered:
                # The existing launch delegates return their answers synchronously
                loop.exec()
            return self._answer
        finally:
            self._loop = None

    @Slot(bool, str)
    def answer(self, accepted: bool, value: str) -> None:
        if self._loop is not None and not self._answered:
            self._answer = value if accepted else None
            self._answered = True
            self._loop.quit()

    @Slot(bool, QUrl)
    def answer_file(self, accepted: bool, url: QUrl) -> None:
        path = url.toLocalFile()
        self.answer(accepted and bool(path), path)

    def dismiss(self) -> None:
        self._notices.clear()
        self.cancelRequested.emit()
        self.answer(False, "")


class QtLaunchUIDelegate(LaunchUIDelegate):
    def __init__(self, prompts: PromptController) -> None:
        self._prompts = prompts

    def show_notice(self, message_markup: str, secondary: str | None = None) -> None:
        self._prompts.notice(message_markup, secondary or "")

    def ask_question(self, title: str, question_markup: str) -> bool:
        return self._prompts.ask("question", title, question_markup) is not None

    def ask_for_text(self, title: str, question_markup: str, initial_value: str = "") -> str | None:
        return self._prompts.ask("text", title, question_markup, initial_value)

    def ask_for_file(self, message: str, default_path: str | None = None) -> str | None:
        folder = ""
        if default_path:
            path = Path(default_path).expanduser().absolute()
            folder = QUrl.fromLocalFile(str(path if path.is_dir() else path.parent)).toString()
        return self._prompts.ask("file", message, "", folder)

    def start_installer(
        self,
        installers: list[dict[str, Any]],
        service: Any = None,
        appid: str | None = None,
        installation_kind: Any = None,
    ) -> None:
        self.show_notice(_("Installing games isn't available in the Qt version of Lutris yet."))
