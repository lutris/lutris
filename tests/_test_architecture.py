"""Keep the core of Lutris independent of its user interface.

Everything outside lutris/gui is the core: games, runners, services, the
installer, the database. A frontend (the GTK one in lutris/gui today, a Qt one
later) drives the core, never the other way round, so the core must not import
lutris.gui or a GUI toolkit. That's what lets a second frontend reuse it, and
lets it run as a separate process later. See docs/architecture.rst.
"""

import ast
from pathlib import Path

LUTRIS_DIR = Path(__file__).resolve().parents[1] / "lutris"
FRONTEND_DIRS = {"gui"}

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
            if node.module == "gi.repository":
                found |= {f"gi.repository.{alias.name}" for alias in node.names if alias.name in UI_NAMESPACES}
        elif isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names if alias.name.startswith("lutris.gui")}
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


def find_core_violations() -> dict[str, set[str]]:
    violations: dict[str, set[str]] = {}
    for path in sorted(LUTRIS_DIR.rglob("*.py")):
        relative = path.relative_to(LUTRIS_DIR.parent)
        if relative.parts[1] in FRONTEND_DIRS:
            continue
        dependencies = find_ui_dependencies(path.read_text(encoding="utf-8"))
        if dependencies:
            violations[relative.as_posix()] = dependencies
    return violations


def test_core_has_no_ui_dependencies():
    violations = find_core_violations()
    assert not violations, (
        "Core modules must not depend on the GUI; move the UI part into lutris/gui, or have the core "
        f"call a delegate or fire a notification the GUI handles instead: {violations}"
    )


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
