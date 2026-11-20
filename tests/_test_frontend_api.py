"""Frontends use the core only through the backend's API (lutris.backend).

That API takes and returns plain data, so the same calls can later reach a
backend in another process (stage 3 in docs/architecture.rst). A frontend that
reaches into Game, runner or service objects, the database or the configuration
directly can't be moved onto IPC, so this test fails when a frontend module
imports a core module other than the API and the support modules below.

KNOWN_VIOLATIONS lists what the GTK frontend uses directly. The GTK frontend is
frozen while the Qt one replaces it, so this only keeps it from getting worse:
the test fails if a new use appears, and also when a listed one is gone, so that
the list only ever shrinks. The command-line and Qt frontends may have none.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIRS = {"gui", "cli", "qt"}

# What frontends may import from the core: the API, and support code that isn't
# about games, runners, services or the library
FRONTEND_API = (
    "lutris.backend",
    "lutris.delegates",
    "lutris.exceptions",
    "lutris.settings",
    "lutris.util.datapath",
    "lutris.util.display_backend",
    "lutris.util.jobs",
    "lutris.util.log",
    "lutris.util.mainloop",
    "lutris.util.notifications",
    "lutris.util.strings",
)

KNOWN_VIOLATIONS: dict[str, set[str]] = {
    "lutris/gui/addgameswindow.py": {
        "lutris.api",
        "lutris.config",
        "lutris.installer",
        "lutris.scanners.playtron",
        "lutris.sysoptions",
        "lutris.util.wine.proton",
        "lutris.util.wine.wine",
    },
    "lutris/gui/application.py": {
        "lutris.api",
        "lutris.database.games",
        "lutris.database.services",
        "lutris.game",
        "lutris.installer",
        "lutris.services",
        "lutris.services.base",
        "lutris.services.gog_cloud_operation",
        "lutris.util.busy",
        "lutris.util.http",
    },
    "lutris/gui/config/accounts_box.py": {
        "lutris.util.steam.config",
    },
    "lutris/gui/config/add_game_dialog.py": {"lutris.config", "lutris.game"},
    "lutris/gui/config/boxes.py": {
        "lutris.config",
        "lutris.game",
        "lutris.runners",
        "lutris.sysoptions",
        "lutris.util.wine.wine",
    },
    "lutris/gui/config/edit_category_games.py": {"lutris.database.categories", "lutris.database.games", "lutris.game"},
    "lutris/gui/config/edit_game_categories.py": {"lutris.database.categories", "lutris.game"},
    "lutris/gui/config/edit_saved_search.py": {
        "lutris.database.categories",
        "lutris.database.games",
        "lutris.database.saved_searches",
        "lutris.runners",
        "lutris.search",
        "lutris.search_predicate",
        "lutris.services",
    },
    "lutris/gui/config/game_common.py": {"lutris.config", "lutris.game", "lutris.runners", "lutris.services.lutris"},
    "lutris/gui/config/game_info_box.py": {
        "lutris.game",
        "lutris.runners",
        "lutris.services.lutris",
        "lutris.services.service_media",
        "lutris.util.images",
    },
    "lutris/gui/config/preferences_dialog.py": {"lutris.config"},
    "lutris/gui/config/runner.py": {"lutris.config", "lutris.runners"},
    "lutris/gui/config/runner_box.py": {"lutris.runners"},
    "lutris/gui/config/runners_box.py": {"lutris.runners", "lutris.search"},
    "lutris/gui/config/services_box.py": {"lutris.services"},
    "lutris/gui/config/storage_box.py": {
        "lutris.cache",
        "lutris.config",
        "lutris.runners.runner",
        "lutris.util.retroarch.firmware",
    },
    "lutris/gui/config/sysinfo_box.py": {"lutris.util.linux", "lutris.util.system", "lutris.util.wine.wine"},
    "lutris/gui/config/updates_box.py": {"lutris.runtime", "lutris.services.lutris"},
    "lutris/gui/config/widget_generator.py": {"lutris.config"},
    "lutris/gui/dialogs/__init__.py": {"lutris.config", "lutris.game"},
    "lutris/gui/dialogs/cache.py": {"lutris.cache"},
    "lutris/gui/dialogs/delegates.py": {
        "lutris.config",
        "lutris.game",
        "lutris.installer",
        "lutris.services.base",
        "lutris.util.downloader",
    },
    "lutris/gui/dialogs/download.py": {"lutris.util.downloader", "lutris.util.file_downloads"},
    "lutris/gui/dialogs/game_import.py": {
        "lutris.config",
        "lutris.database.games",
        "lutris.game",
        "lutris.scanners.default_installers",
        "lutris.scanners.tosec",
        "lutris.services.lutris",
        "lutris.util.path_cache",
        "lutris.util.system",
    },
    "lutris/gui/dialogs/issue.py": {"lutris.util.linux"},
    "lutris/gui/dialogs/log.py": {"lutris.game", "lutris.util.log_buffer"},
    "lutris/gui/dialogs/move_game.py": {"lutris.game", "lutris.util.path_cache"},
    "lutris/gui/dialogs/runner_install.py": {
        "lutris.api",
        "lutris.database.games",
        "lutris.game",
        "lutris.util.downloader",
        "lutris.util.extract",
        "lutris.util.system",
        "lutris.util.wine.wine",
    },
    "lutris/gui/dialogs/uninstall_dialog.py": {
        "lutris.database.games",
        "lutris.game",
        "lutris.util.path_cache",
        "lutris.util.system",
    },
    "lutris/gui/dialogs/webconnect_dialog.py": {"lutris.config", "lutris.services.base", "lutris.util.http"},
    "lutris/gui/display_backend.py": {"lutris.util.graphics.xrandr"},
    "lutris/gui/exception_backstops.py": {"lutris.installer.errors"},
    "lutris/gui/game_actions.py": {
        "lutris.config",
        "lutris.database.games",
        "lutris.game",
        "lutris.monitored_command",
        "lutris.services",
        "lutris.services.base",
        "lutris.services.lutris",
        "lutris.util.standalone_scripts",
        "lutris.util.steam.shortcut",
        "lutris.util.system",
        "lutris.util.xdgshortcuts",
    },
    "lutris/gui/installer/file_box.py": {
        "lutris.installer.installer_file_collection",
        "lutris.installer.steam_installer",
        "lutris.util.system",
    },
    "lutris/gui/installerwindow.py": {
        "lutris.config",
        "lutris.game",
        "lutris.installer",
        "lutris.installer.errors",
        "lutris.installer.interpreter",
        "lutris.util.linux",
        "lutris.util.log_buffer",
        "lutris.util.steam.shortcut",
        "lutris.util.system",
        "lutris.util.xdgshortcuts",
    },
    "lutris/gui/lutriswindow.py": {
        "lutris.api",
        "lutris.database.categories",
        "lutris.database.games",
        "lutris.database.saved_searches",
        "lutris.database.services",
        "lutris.game",
        "lutris.runtime",
        "lutris.services",
        "lutris.services.base",
        "lutris.services.gog_cloud_operation",
        "lutris.services.lutris",
        "lutris.util.busy",
        "lutris.util.linux",
        "lutris.util.path_cache",
        "lutris.util.progress_info",
        "lutris.util.system",
        "lutris.util.wine.wine",
    },
    "lutris/gui/views/base.py": {
        "lutris.database.games",
        "lutris.database.services",
        "lutris.game",
        "lutris.services.service_media",
        "lutris.util.path_cache",
    },
    "lutris/gui/views/store.py": {"lutris.services.base", "lutris.services.service_media"},
    "lutris/gui/views/store_item.py": {
        "lutris.database.services",
        "lutris.services",
        "lutris.services.lutris",
        "lutris.services.service_media",
    },
    "lutris/gui/widgets/cellrenderers.py": {
        "lutris.services.service_media",
        "lutris.util.images",
        "lutris.util.path_cache",
    },
    "lutris/gui/widgets/common.py": {"lutris.util.linux", "lutris.util.system"},
    "lutris/gui/widgets/download_progress_box.py": {"lutris.util.file_downloads"},
    "lutris/gui/widgets/game_bar.py": {"lutris.database.games", "lutris.game", "lutris.runners", "lutris.services"},
    "lutris/gui/widgets/log_text_view.py": {"lutris.util.log_buffer"},
    "lutris/gui/widgets/progress_box.py": {"lutris.util.progress_info"},
    "lutris/gui/widgets/scaled_image.py": {"lutris.services.service_media", "lutris.util.images"},
    "lutris/gui/widgets/sidebar.py": {
        "lutris.config",
        "lutris.database.categories",
        "lutris.database.games",
        "lutris.database.saved_searches",
        "lutris.installer.interpreter",
        "lutris.runners",
        "lutris.services",
        "lutris.services.base",
    },
    "lutris/gui/widgets/status_icon.py": {
        "lutris.database.categories",
        "lutris.database.games",
        "lutris.game",
        "lutris.util.display",
    },
    "lutris/gui/widgets/utils.py": {"lutris.util.system"},
}


def _is_module(name: str) -> bool:
    path = ROOT / Path(*name.split("."))
    return path.with_suffix(".py").exists() or (path / "__init__.py").exists()


def find_imported_modules(source: str, package: str) -> set[str]:
    """Return the modules a module's source imports, wherever the import is, with
    relative imports resolved against package and `from x import y` resolved to x.y
    when y is a module."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")
                parts = parts[: len(parts) - node.level + 1]
                base = ".".join([*parts, base] if base else parts)
            for alias in node.names:
                full_name = f"{base}.{alias.name}"
                found.add(full_name if _is_module(full_name) else base)
    return found


def is_allowed(module: str) -> bool:
    """True if a frontend may import a module: a frontend's own, the API, or anything
    not from Lutris."""
    if not module.startswith("lutris."):
        return module != "lutris"
    if module.split(".")[1] in FRONTEND_DIRS:
        return True
    return any(module == allowed or module.startswith(allowed + ".") for allowed in FRONTEND_API)


def find_frontend_violations() -> dict[str, set[str]]:
    violations: dict[str, set[str]] = {}
    for path in sorted((ROOT / "lutris").rglob("*.py")):
        relative = path.relative_to(ROOT)
        if relative.parts[1] not in FRONTEND_DIRS:
            continue
        package = ".".join(relative.with_suffix("").parts[:-1])
        used = {m for m in find_imported_modules(path.read_text(encoding="utf-8"), package) if not is_allowed(m)}
        if used:
            violations[relative.as_posix()] = used
    return violations


def test_frontends_gain_no_new_core_dependencies():
    violations = find_frontend_violations()
    new = {
        module: used - KNOWN_VIOLATIONS.get(module, set())
        for module, used in violations.items()
        if used - KNOWN_VIOLATIONS.get(module, set())
    }
    assert not new, (
        "Frontends must use the core through lutris.backend; add the call you need to the backend's API "
        f"instead of importing these: {new}"
    )


def test_known_violations_are_still_current():
    violations = find_frontend_violations()
    fixed = {
        module: used - violations.get(module, set())
        for module, used in KNOWN_VIOLATIONS.items()
        if used - violations.get(module, set())
    }
    assert not fixed, f"These are no longer used, so remove them from KNOWN_VIOLATIONS: {fixed}"


def test_the_command_line_and_qt_frontends_use_only_the_api():
    violations = find_frontend_violations()
    assert not {module: used for module, used in violations.items() if module.startswith(("lutris/cli/", "lutris/qt/"))}


def test_finds_every_kind_of_import():
    source = """
from lutris import settings
from lutris.game import Game
from ..util.busy import BusyAsyncCall
import lutris.runners

def later():
    from lutris.backend import games
"""
    assert find_imported_modules(source, "lutris.gui.dialogs") == {
        "lutris.settings",
        "lutris.game",
        "lutris.gui.util.busy",
        "lutris.runners",
        "lutris.backend.games",
    }
    assert not is_allowed("lutris.game")
    assert is_allowed("lutris.backend.games")
    assert is_allowed("lutris.gui.dialogs")
    assert is_allowed("gi.repository")
