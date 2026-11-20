"""Prevent GUI imports in the core and keep the graphical frontend in Qt Quick."""

import ast

from tests._test_frontend_api import FRONTEND_DIRS, ROOT, find_imported_modules

GTK_NAMESPACES = {
    "AppIndicator3",
    "AyatanaAppIndicator3",
    "Gdk",
    "GdkPixbuf",
    "GdkX11",
    "GnomeDesktop",
    "Gtk",
    "Handy",
    "Notify",
    "Pango",
    "PangoCairo",
    "WebKit",
    "WebKit2",
}
NATIVE_QT_IMPORTS = {
    "lutris/qt/application.py": {"PySide6.QtWidgets.QApplication"},
    "lutris/qt/tray.py": {"PySide6.QtWidgets.QMenu", "PySide6.QtWidgets.QSystemTrayIcon"},
}
QUICK_MODULES = {"PySide6.QtCore", "PySide6.QtGui", "PySide6.QtQml", "PySide6.QtQuick"}
GIO_DEFAULT = "Gio.Application.get_default()"


def find_ui_dependencies(source: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module in ("PySide6", "PySide6.QtWidgets", "gi.repository"):
                found.update(f"{node.module}.{alias.name}" for alias in node.names)
            else:
                found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                node.func.attr == "require_version"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value in GTK_NAMESPACES
            ):
                found.add(f"gi.repository.{node.args[0].value}")
            if node.func.attr == "get_default" and ast.unparse(node.func.value) in ("Gio.Application", "Application"):
                found.add(GIO_DEFAULT)
    return {
        name
        for name in found
        if name.split(".", 1)[0] in {"PySide6", "PyQt6", "PyQt5", "PySide2", "tkinter"}
        or (name.startswith("gi.repository.") and name.split(".")[2] in GTK_NAMESPACES)
        or name == GIO_DEFAULT
    }


def test_toolkit_and_frontend_boundaries():
    violations: dict[str, set[str]] = {}
    for path in (ROOT / "lutris").rglob("*.py"):
        relative = path.relative_to(ROOT)
        name = relative.as_posix()
        frontend = relative.parts[1]
        source = path.read_text(encoding="utf-8")
        forbidden = find_ui_dependencies(source)
        modules = find_imported_modules(source, ".".join(relative.parts[:-1]))
        forbidden |= {module for module in modules if module == "lutris.gui" or module.startswith("lutris.gui.")}
        if frontend == "qt":
            forbidden = {module for module in forbidden if ".".join(module.split(".")[:2]) not in QUICK_MODULES}
            forbidden -= NATIVE_QT_IMPORTS.get(name, set()) | {GIO_DEFAULT}
        elif frontend not in FRONTEND_DIRS:
            forbidden |= {
                module for module in modules if module.split(".")[:2] in (["lutris", part] for part in FRONTEND_DIRS)
            }
            if name == "lutris/launcher.py":
                forbidden -= {"lutris.cli.application", "lutris.qt.application"}
        if forbidden:
            violations[name] = forbidden
    assert not violations, f"GUI dependencies belong in Qt Quick: {violations}"


def test_only_qt_quick_assets_are_shipped():
    assert not (ROOT / "lutris/gui").exists()
    assert not (ROOT / "lutris/data/ui").exists()
    for path in (ROOT / "lutris/qt/qml").rglob("*.qml"):
        assert not any(
            line.lstrip().startswith(("import QtWebEngine", "import QtWebView"))
            for line in path.read_text(encoding="utf-8").splitlines()
        ), path


def test_finds_toolkit_imports_even_inside_functions():
    source = """
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gdk
from PySide6 import QtCore
from PySide6.QtWidgets import QWidget, QApplication

def later():
    import PySide6.QtWebEngineQuick
    return Gio.Application.get_default()
"""
    assert find_ui_dependencies(source) == {
        "gi.repository.Gtk",
        "gi.repository.Gdk",
        "PySide6.QtCore",
        "PySide6.QtWidgets.QWidget",
        "PySide6.QtWidgets.QApplication",
        "PySide6.QtWebEngineQuick",
        GIO_DEFAULT,
    }
