"""The commands that need no GUI, run through lutris.cli.commands."""

import pytest
from gi.repository import GLib

from lutris.cli.commands import run_text_command
from lutris.cli.options import is_text_command
from lutris.cli.output import CommandOutput
from lutris.delegates import LaunchUIDelegate
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class FakeOutput(CommandOutput):
    """Collects what a command prints, as if it ran in /work."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.errors: list[str] = []

    def print(self, text: str) -> None:
        self.lines.append(text)

    def print_error(self, text: str) -> None:
        self.errors.append(text)

    def ask_yes_or_no(self, question: str) -> bool:
        return False

    def get_path(self, path: str) -> str:
        return path if path.startswith("/") else "/work/" + path


def make_options(**values: str | bool) -> GLib.VariantDict:
    """Parsed options as Gio passes them, from keyword arguments named like the options."""
    options = GLib.VariantDict.new(None)
    for name, value in values.items():
        variant = GLib.Variant("b", value) if isinstance(value, bool) else GLib.Variant("s", value)
        options.insert_value(name.replace("_", "-"), variant)
    return options


def run(**values: str | bool) -> tuple[int | None, FakeOutput]:
    output = FakeOutput()
    return run_text_command(make_options(**values), output, LaunchUIDelegate()), output


def test_text_commands_are_told_from_graphical_ones():
    assert is_text_command(make_options(list_games=True, json=True))
    assert is_text_command(make_options(export="some-game"))
    assert not is_text_command(make_options(debug=True))
    assert not is_text_command(make_options(install="game.yml"))


def test_options_without_a_text_command_are_left_to_the_gui():
    status, output = run(debug=True, json=True)
    assert status is None
    assert output.lines == output.errors == []


def test_runners_are_listed_on_the_invoking_terminal():
    status, output = run(list_runners=True)
    assert status == 0
    assert "wine" in output.lines
    assert output.lines == sorted(output.lines, key=str.lower)


def test_export_needs_a_destination():
    status, output = run(export="some-game")
    assert status == 1
    assert output.errors == ["No destination dir given"]


def test_import_reads_paths_from_the_invoking_directory(monkeypatch):
    imported: list[tuple[str, str]] = []
    monkeypatch.setattr("lutris.cli.commands.import_game", lambda path, dest: imported.append((path, dest)))

    status, _output = run(dest="games", **{"import": "game.tar.xz"})
    assert status == 0
    assert imported == [("/work/game.tar.xz", "/work/games")]


def test_script_for_an_unknown_game_fails():
    status, _output = run(output_script="no-such-game")
    assert status == 1


@pytest.mark.parametrize("answer", [True, False])
def test_uninstalling_wine_asks_first(monkeypatch, answer):
    uninstalled: list[str] = []
    monkeypatch.setattr("lutris.cli.runners.uninstall_runner_by_name", lambda _output, name: uninstalled.append(name))
    monkeypatch.setattr(FakeOutput, "ask_yes_or_no", lambda _self, _question: answer)

    status, _output = run(uninstall_runner="wine")
    assert status == 0
    assert uninstalled == (["wine"] if answer else [])
