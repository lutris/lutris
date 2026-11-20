"""The Lutris Qt Quick style draws every control, with icons that exist."""

import re
from pathlib import Path

import pytest

from lutris.qt import sidebar
from lutris.qt.main_window import QML_DIR, STYLE

ICONS = QML_DIR / STYLE / "icons"
# Literal icon names, in Theme.icon("…") calls, Icon symbols and the icon fields of page lists
ICON_REFERENCES = re.compile(r'Theme\.icon\("([^"]+)"\)|symbol: "([^"]+)"|\bicon: "([^"]+)"')
# Names a view builds at runtime, such as the layout switcher's
RUNTIME_ICONS = {"covers", "banners", "list", "favorite-filled", "visible", "hidden"}


def referenced_icons() -> dict[str, set[Path]]:
    names: dict[str, set[Path]] = {}
    for path in QML_DIR.rglob("*.qml"):
        for match in ICON_REFERENCES.finditer(path.read_text(encoding="utf-8")):
            names.setdefault(next(group for group in match.groups() if group), set()).add(path)
    return names


def test_every_referenced_icon_is_in_the_icon_set() -> None:
    names = set(referenced_icons()) | RUNTIME_ICONS
    names |= {sidebar.get_view_icon(view) for view in sidebar_views()}
    missing = sorted(name for name in names if not (ICONS / f"{name}.svg").is_file())
    assert not missing, f"Icons missing from {ICONS}: {missing}"


def test_the_style_module_declares_its_theme_and_falls_back_to_basic() -> None:
    qmldir = (QML_DIR / STYLE / "qmldir").read_text(encoding="utf-8").splitlines()
    assert qmldir[0] == f"module {STYLE}"
    assert "singleton Theme 1.0 Theme.qml" in qmldir
    assert "import QtQuick.Controls.Basic auto" in qmldir


def test_views_use_the_style_rather_than_pinning_basic() -> None:
    pinned = [
        path.name
        for path in QML_DIR.glob("*.qml")
        if "import QtQuick.Controls.Basic" in path.read_text(encoding="utf-8")
    ]
    assert not pinned


def sidebar_views() -> list[dict[str, str]]:
    return [
        {"category": "all"},
        {"dynamic_category": "recent"},
        {"dynamic_category": "running"},
        {"category": "favorite"},
        {"dynamic_category": ".uncategorized"},
        {"dynamic_category": "missing"},
        {"category": ".hidden"},
        {"category": "Arcade"},
        {"saved_search": "Unplayed"},
        {"service": "gog"},
        {"runner": "wine"},
        {"platform": "Linux"},
    ]


@pytest.mark.parametrize(
    ("view", "icon"),
    [
        ({"category": "all"}, "games"),
        ({"dynamic_category": "recent"}, "recent"),
        ({"category": ".hidden"}, "hidden"),
        ({"category": "Arcade"}, "category"),
        ({"category": "missing"}, "category"),
        ({"saved_search": "Unplayed"}, "saved-search"),
        ({"service": "gog"}, "store"),
        ({"runner": "wine"}, "runner"),
        ({"platform": "Linux"}, "platform"),
    ],
)
def test_sidebar_views_have_icons(view: dict[str, str], icon: str) -> None:
    assert sidebar.get_view_icon(view) == icon
