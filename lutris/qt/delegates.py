"""Bridge synchronous launch prompts to QML dialogs."""

from collections import deque
from collections.abc import Callable
from gettext import gettext as _
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEventLoop, QObject, QUrl, Signal, Slot

from lutris.backend.launch_configurations import BackendLaunchUIDelegate, LaunchChoice
from lutris.backend.models import GameInfo
from lutris.exceptions import LutrisError

type Notice = tuple[str, str, str, bool]


class PromptController(QObject):
    noticeRequested = Signal(str, str, str, bool)
    inputRequested = Signal(str, str, str, str)
    configurationRequested = Signal(str, list, int, bool)
    cancelRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._notices: deque[Notice] = deque()
        self._notice_open = False
        self._loop: QEventLoop | None = None
        self._answer: str | LaunchChoice | None = None
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
        answer = self._wait_for_answer(lambda: self.inputRequested.emit(kind, title, message, initial))
        return answer if isinstance(answer, str) else None

    def choose_configuration(
        self, title: str, names: tuple[str, ...], current_index: int | None
    ) -> LaunchChoice | None:
        answer = self._wait_for_answer(
            lambda: self.configurationRequested.emit(title, list(names), current_index or 0, current_index is not None)
        )
        return answer if isinstance(answer, LaunchChoice) else None

    def _wait_for_answer(self, request: Callable[[], None]) -> str | LaunchChoice | None:
        if self._loop is not None:
            return None
        loop = QEventLoop()
        self._loop = loop
        self._answer = None
        self._answered = False
        try:
            request()
            if not self._answered:
                # The existing launch delegates return their answers synchronously
                loop.exec()
            return self._answer
        finally:
            self._loop = None

    @Slot(bool, str)
    def answer(self, accepted: bool, value: str) -> None:
        self._finish_answer(value if accepted else None)

    @Slot(int, bool)
    def answer_configuration(self, index: int, remember: bool) -> None:
        self._finish_answer(LaunchChoice(index, remember))

    def _finish_answer(self, answer: str | LaunchChoice | None) -> None:
        if self._loop is not None and not self._answered:
            self._answer = answer
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


class QtLaunchUIDelegate(BackendLaunchUIDelegate):
    def __init__(self, prompts: PromptController, *, choose_again: bool = False) -> None:
        super().__init__(choose_again=choose_again)
        self._prompts = prompts

    def choose_launch_configuration(
        self, game: GameInfo, names: tuple[str, ...], current_index: int | None
    ) -> LaunchChoice | None:
        return self._prompts.choose_configuration(_("Launch %s") % game.name, names, current_index)

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
