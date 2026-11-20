"""Load and own the Qt Quick library window."""

from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

from lutris.qt.delegates import PromptController
from lutris.qt.library_controller import LibraryController


class MainWindow(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.engine = QQmlApplicationEngine(self)
        self.prompts = PromptController()
        self.prompts.setParent(self)
        self.controller = LibraryController(self.prompts)
        self.controller.setParent(self)
        self.engine.setInitialProperties({"controller": self.controller, "prompts": self.prompts})
        self.engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name("qml") / "Main.qml")))
        root = next(iter(self.engine.rootObjects()), None)
        if not isinstance(root, QQuickWindow):
            self.controller.shutdown()
            raise RuntimeError("Could not load the Lutris QML window")
        self.window = root
        self.window.visibleChanged.connect(lambda: self.prompts.set_interactive(self.window.isVisible()))
        self.load_task = self.controller.start()

    def show(self) -> None:
        self.window.show()
        self.window.raise_()
        self.window.requestActivate()

    def shutdown(self) -> None:
        self.prompts.set_interactive(False)
        self.controller.shutdown()
        self.prompts.dismiss()
        self.window.close()
