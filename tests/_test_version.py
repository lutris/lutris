import sys
import types
from pathlib import Path

import pytest

from lutris import __version__, version


def test_version_matches_pyproject():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    assert __version__ == version.read_project_version(pyproject_path)


@pytest.mark.parametrize("app_version", ["0.5.23", "0.5.23.post1"])
def test_release_artifact_version_is_unchanged(app_version):
    assert version.build_artifact_version(app_version, {}) == app_version


@pytest.mark.parametrize("app_version", ["0.6.0a1", "0.6.0b1", "0.6.0rc1", "0.6.0.dev1"])
def test_local_prerelease_artifact_version(app_version):
    assert version.build_artifact_version(app_version, {}) == f"{app_version}+local"


def test_github_prerelease_artifact_version_uses_short_sha():
    environment = {"GITHUB_ACTIONS": "true", "GITHUB_SHA": "ABCDEF0123456789ABCDEF0123456789ABCDEF01"}
    assert version.build_artifact_version("0.6.0b1", environment) == "0.6.0b1+gabcdef0"


@pytest.mark.parametrize("github_sha", ["", "123456", "not-a-git-sha"])
def test_github_prerelease_artifact_version_rejects_invalid_sha(github_sha):
    environment = {"GITHUB_ACTIONS": "true", "GITHUB_SHA": github_sha}
    with pytest.raises(ValueError, match="GITHUB_SHA"):
        version.build_artifact_version("0.6.0b1", environment)


def test_artifact_version_rejects_local_metadata():
    with pytest.raises(ValueError, match="must not contain local metadata"):
        version.build_artifact_version("0.6.0b1+custom", {})


def test_pyproject_of_another_project_is_rejected(tmp_path):
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text('[project]\nname = "unrelated"\nversion = "1.0.0"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="does not describe"):
        version.read_project_version(pyproject_path)


def test_source_version_comes_from_pyproject(monkeypatch, tmp_path):
    module_path = tmp_path / "lutris" / "version.py"
    module_path.parent.mkdir()
    module_path.touch()
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "lutris"\nversion = "1.2.3"\n', encoding="utf-8")
    monkeypatch.setattr(version, "__file__", str(module_path))
    monkeypatch.setattr(version, "_read_installed_version", lambda: "0.1.0")

    assert version.read_version() == "1.2.3"


def test_unrelated_parent_pyproject_is_ignored(monkeypatch, tmp_path):
    # An installed copy nested somewhere under another project's tree
    module_path = tmp_path / "site-packages" / "lutris" / "version.py"
    module_path.parent.mkdir(parents=True)
    module_path.touch()
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "lutris"\nversion = "9.9.9"\n', encoding="utf-8")
    monkeypatch.setattr(version, "__file__", str(module_path))
    monkeypatch.setattr(version, "_read_installed_version", lambda: "1.2.3")

    assert version.read_version() == "1.2.3"


def test_installed_version_comes_from_optional_settings(monkeypatch):
    monkeypatch.setattr(version, "_read_source_version", lambda: None)
    monkeypatch.setitem(sys.modules, "lutris.optional_settings", types.SimpleNamespace(VERSION="1.2.3"))

    assert version.read_version() == "1.2.3"


def test_unknown_version_without_any_source(monkeypatch):
    monkeypatch.setattr(version, "_read_source_version", lambda: None)
    monkeypatch.setattr(version, "_read_installed_version", lambda: None)

    assert version.read_version() == version.UNKNOWN_VERSION
