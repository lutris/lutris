"""Keep the core of Lutris independent of its user interface.

Everything outside the frontends is the core: games, runners, services, the
installer, the database. A frontend (the GTK one in lutris/gui, the command-line
one in lutris/cli, the Qt one in lutris/qt) drives the core, never the other way round, so
the core must not import a frontend or a GUI toolkit. That's what lets a second
frontend reuse it, and lets it run as a separate process later. The command-line
frontend must work with no GUI toolkit installed, so it must not import one either.
See docs/architecture.rst.
"""

import ast
from collections.abc import Callable
from pathlib import Path

LUTRIS_DIR = Path(__file__).resolve().parents[1] / "lutris"
FRONTEND_DIRS = {"gui", "cli", "qt"}

# GObject introspection namespaces that belong to a UI toolkit. GLib, GObject and
# Gio are fine in the core; they aren't UI
UI_NAMESPACES = {
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
    "WebKit2",
}


def find_ui_dependencies(source: str) -> set[str]:
    """Return what a module's source imports from the UI, wherever the import is."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "lutris.gui" or node.module.startswith("lutris.gui."):
                found.add(node.module)
            if node.module == "PySide6.QtWidgets" or (
                node.module == "PySide6" and any(alias.name == "QtWidgets" for alias in node.names)
            ):
                found.add("PySide6.QtWidgets")
            if node.module == "gi.repository":
                found |= {f"gi.repository.{alias.name}" for alias in node.names if alias.name in UI_NAMESPACES}
        elif isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names if alias.name.startswith(("lutris.gui", "PySide6.QtWidgets"))}
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "require_version"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value in UI_NAMESPACES
        ):
            found.add(f"gi.require_version({node.args[0].value})")
        elif (
            # The running application is the frontend's, even though Gio isn't UI
            isinstance(node, ast.Attribute)
            and node.attr == "get_default"
            and ast.unparse(node.value) in ("Gio.Application", "Application")
        ):
            found.add("Gio.Application.get_default()")
    return found


def find_frontend_imports(source: str) -> set[str]:
    """Return the frontend modules a module's source imports."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            continue
        found |= {name for name in names if name.split(".")[:2] in (["lutris", d] for d in FRONTEND_DIRS)}
    return found


def find_violations(checks: Callable[[str], bool], find: Callable[[str], set[str]]) -> dict[str, set[str]]:
    """Run find on each module whose top-level name under lutris/ checks accepts,
    and return what it found by module."""
    violations: dict[str, set[str]] = {}
    for path in sorted(LUTRIS_DIR.rglob("*.py")):
        relative = path.relative_to(LUTRIS_DIR.parent)
        if not checks(relative.parts[1]):
            continue
        dependencies = find(path.read_text(encoding="utf-8"))
        if dependencies:
            violations[relative.as_posix()] = dependencies
    return violations


def test_core_has_no_ui_dependencies():
    violations = find_violations(
        lambda name: name not in FRONTEND_DIRS,
        lambda source: find_ui_dependencies(source) | find_frontend_imports(source),
    )
    assert not violations, (
        "Core modules must not depend on a frontend; move the UI part into the frontend, or have the core "
        f"call a delegate or fire a notification the frontend handles instead: {violations}"
    )


def test_qt_frontend_uses_qt_quick():
    violations = find_violations(
        lambda name: name == "qt",
        lambda source: find_ui_dependencies(source) - {"Gio.Application.get_default()"},
    )
    assert not violations, f"The Qt frontend must use Qt Quick for its UI: {violations}"


def test_command_line_needs_no_gui():
    violations = find_violations(lambda name: name == "cli", find_ui_dependencies)
    assert not violations, f"The command-line frontend must work with no GUI toolkit installed: {violations}"


def test_finds_every_kind_of_ui_dependency():
    source = """
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from lutris.gui.dialogs import ErrorDialog

def later():
    import lutris.gui.application
    return Gio.Application.get_default()
"""
    assert find_ui_dependencies(source) == {
        "gi.require_version(Gtk)",
        "gi.repository.Gtk",
        "lutris.gui.dialogs",
        "lutris.gui.application",
        "Gio.Application.get_default()",
    }


def test_finds_frontend_imports():
    source = """
from lutris.cli.output import CommandOutput
import lutris.gui.application
from lutris.game import Game
"""
    assert find_frontend_imports(source) == {"lutris.cli.output", "lutris.gui.application"}
