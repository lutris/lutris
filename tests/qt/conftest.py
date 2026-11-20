"""Run the Qt Quick frontend with the offscreen platform and software renderer."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from lutris.qt.translations import QmlTranslator  # noqa: E402


@pytest.fixture(scope="session")
def qt_application() -> QGuiApplication:
    application = QGuiApplication.instance()
    assert application is None or isinstance(application, QGuiApplication)
    application = application or QGuiApplication([])
    application.installTranslator(QmlTranslator(application))
    return application
