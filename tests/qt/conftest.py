"""The Qt frontend's tests need PySide6 (`uv sync --extra qt`), and run offscreen."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qt_application():
    return QApplication.instance() or QApplication([])
