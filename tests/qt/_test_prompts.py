"""Resolve worker requests on the Qt thread without hanging on shutdown."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from PySide6.QtCore import QEventLoop, QThread, QTimer
from PySide6.QtGui import QGuiApplication

from lutris.qt.delegates import PromptController


@pytest.mark.parametrize("close_window", [False, True])
def test_cloud_conflict_worker_waits_for_gui_or_shutdown(qt_application: QGuiApplication, close_window: bool) -> None:
    prompts = PromptController()
    prompts.set_interactive(True)
    loop = QEventLoop()
    requests: list[tuple[str, str]] = []

    def respond(game: str, location: str) -> None:
        assert QThread.currentThread() == qt_application.thread()
        requests.append((game, location))
        if close_window:
            prompts.set_interactive(False)
            prompts.dismiss()
        else:
            prompts.answer(True, "download")
        loop.quit()

    prompts.conflictRequested.connect(respond)
    with ThreadPoolExecutor(max_workers=1) as worker:
        result = worker.submit(prompts.resolve_cloud_conflict, "Game", "saves")
        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit)
        deadline.start(2000)
        loop.exec()
        try:
            assert result.result(timeout=1) == (None if close_window else "download")
        finally:
            prompts.set_interactive(False)
    assert requests == [("Game", "saves")]
    assert prompts.resolve_cloud_conflict("Game", "saves") is None
