"""Keep the core of Lutris independent of its user interface.

Everything outside lutris/gui is the core: games, runners, services, the
installer, the database. A frontend (the GTK one in lutris/gui today, a Qt one
later) drives the core, never the other way round, so the core must not import
lutris.gui or a GUI toolkit. That's what lets a second frontend reuse it, and
lets it run as a separate process later. See docs/architecture.rst.

KNOWN_VIOLATIONS lists the couplings that predate this rule. The test fails if
a new one appears, and also when one listed here is gone, so that the list only
ever shrinks: remove the entry when you untangle a module.
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

KNOWN_VIOLATIONS: dict[str, set[str]] = {
    "lutris/__init__.py": {"gi.require_version(Gdk)", "gi.require_version(Gtk)"},
    "lutris/exception_backstops.py": {"gi.repository.Gtk", "lutris.gui.dialogs", "lutris.gui.widgets.utils"},
    "lutris/game.py": {"lutris.gui.application", "lutris.gui.dialogs.cloud_sync_progress", "lutris.gui.widgets.utils"},
    "lutris/installer/errors.py": {"lutris.gui.dialogs"},
    "lutris/runners/wine.py": {"lutris.gui.dialogs"},
    "lutris/services/base.py": {
        "lutris.gui.dialogs",
        "lutris.gui.dialogs.webconnect_dialog",
        "lutris.gui.views.media_loader",
        "lutris.gui.widgets.utils",
    },
    "lutris/services/ea_app.py": {"lutris.gui.widgets.utils"},
    "lutris/services/egs.py": {"lutris.gui.widgets.utils"},
    "lutris/services/gog_cloud_hooks.py": {"lutris.gui.dialogs.cloud_sync"},
    "lutris/services/humblebundle.py": {"gi.repository.Gtk", "lutris.gui.dialogs"},
    "lutris/services/itchio.py": {"gi.repository.Gtk", "lutris.gui.dialogs"},
    "lutris/services/lutris.py": {"lutris.gui", "lutris.gui.views.media_loader"},
    "lutris/startup.py": {"gi.repository.GdkPixbuf", "gi.require_version(GdkPixbuf)"},
    "lutris/util/display.py": {
        "gi.repository.Gdk",
        "gi.repository.GnomeDesktop",
        "gi.repository.Gtk",
        "gi.require_version(GnomeDesktop)",
        "lutris.gui.application",
    },
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


def test_core_gains_no_new_ui_dependencies():
    violations = find_core_violations()
    new = {
        module: dependencies - KNOWN_VIOLATIONS.get(module, set())
        for module, dependencies in violations.items()
        if dependencies - KNOWN_VIOLATIONS.get(module, set())
    }
    assert not new, (
        "Core modules must not depend on the GUI; move the UI part into lutris/gui, or have the core "
        f"call a delegate or fire a notification the GUI handles instead: {new}"
    )


def test_known_violations_are_still_current():
    violations = find_core_violations()
    fixed = {
        module: dependencies - violations.get(module, set())
        for module, dependencies in KNOWN_VIOLATIONS.items()
        if dependencies - violations.get(module, set())
    }
    assert not fixed, f"These are no longer used, so remove them from KNOWN_VIOLATIONS: {fixed}"


def test_finds_every_kind_of_ui_dependency():
    source = """
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from lutris.gui.dialogs import ErrorDialog

def later():
    import lutris.gui.application
"""
    assert find_ui_dependencies(source) == {
        "gi.require_version(Gtk)",
        "gi.repository.Gtk",
        "lutris.gui.dialogs",
        "lutris.gui.application",
    }
