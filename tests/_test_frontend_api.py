"""Keep CLI and Qt on the plain-data backend API."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIRS = {"cli", "qt"}
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


def find_imported_modules(source: str, package: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")
                base = ".".join([*parts[: len(parts) - node.level + 1], *([base] if base else [])])
            for alias in node.names:
                full_name = f"{base}.{alias.name}"
                path = ROOT.joinpath(*full_name.split("."))
                if full_name == "lutris.gui" or path.with_suffix(".py").is_file() or path.is_dir():
                    found.add(full_name)
                else:
                    found.add(base)
    return found


def is_allowed(module: str, frontend: str) -> bool:
    if not module.startswith("lutris."):
        return module != "lutris"
    allowed = (*FRONTEND_API, f"lutris.{frontend}")
    if frontend == "qt":
        allowed = (*allowed, "lutris.cli")
    return any(module == prefix or module.startswith(prefix + ".") for prefix in allowed)


def test_frontends_use_only_the_backend_api():
    violations: dict[str, set[str]] = {}
    for frontend in FRONTEND_DIRS:
        for path in (ROOT / "lutris" / frontend).rglob("*.py"):
            relative = path.relative_to(ROOT)
            package = ".".join(relative.parts[:-1])
            imports = find_imported_modules(path.read_text(encoding="utf-8"), package)
            if forbidden := {module for module in imports if not is_allowed(module, frontend)}:
                violations[relative.as_posix()] = forbidden
    assert not violations, f"Frontends must use the core through lutris.backend: {violations}"


def test_finds_absolute_and_relative_imports():
    source = """
from lutris import settings
from lutris.game import Game
from .tasks import start_task
from ..backend import games
import lutris.runners
"""
    assert find_imported_modules(source, "lutris.qt") == {
        "lutris.settings",
        "lutris.game",
        "lutris.qt.tasks",
        "lutris.backend.games",
        "lutris.runners",
    }
    assert not is_allowed("lutris.game", "qt")
    assert not is_allowed("lutris.qt.application", "cli")
