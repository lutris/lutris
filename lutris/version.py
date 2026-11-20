"""The Lutris version, read from its one canonical place.

The version lives in pyproject.toml and is bumped with `uv version`. Running from a
checkout reads it from there; an installed build uses the distribution metadata.

Run as a script, this resolves the version CI labels build artifacts with:
`python lutris/version.py --artifact-version 0.6.0b1`.

This module must stay importable on its own (no lutris imports), since CI runs it
as a plain script.
"""

import argparse
import os
import re
import tomllib
from collections.abc import Mapping, Sequence
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version
from pathlib import Path

from packaging.version import InvalidVersion, Version

PROJECT_NAME = "lutris"
UNKNOWN_VERSION = "0.0.0"
_GITHUB_SHA_PATTERN = re.compile(r"[0-9a-fA-F]{7,64}")


def read_project_version(pyproject_path: Path) -> str:
    """Read and validate the version from a pyproject.toml describing Lutris."""
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = pyproject.get("project")
    if not isinstance(project, dict) or project.get("name") != PROJECT_NAME:
        raise ValueError(f"{pyproject_path} does not describe the {PROJECT_NAME} project")

    project_version = project.get("version")
    if not isinstance(project_version, str) or not project_version:
        raise ValueError(f"{pyproject_path} does not contain a project version")

    Version(project_version)
    return project_version


def build_artifact_version(app_version: str, environment: Mapping[str, str] | None = None) -> str:
    """Return the version a build artifact is labelled with.

    Releases keep their version as is. Prereleases and dev releases get the commit
    they were built from appended (`+g1a2b3c4`) when built on GitHub Actions, or
    `+local` otherwise, so two builds of the same prerelease can be told apart.
    """
    parsed = Version(app_version)
    if parsed.local is not None:
        raise ValueError("The canonical project version must not contain local metadata")
    if not (parsed.is_prerelease or parsed.is_devrelease):
        return app_version

    build_environment = os.environ if environment is None else environment
    if build_environment.get("GITHUB_ACTIONS") != "true":
        return f"{app_version}+local"

    github_sha = build_environment.get("GITHUB_SHA", "")
    if _GITHUB_SHA_PATTERN.fullmatch(github_sha) is None:
        raise ValueError("GITHUB_SHA must contain between 7 and 64 hexadecimal characters when GITHUB_ACTIONS=true")
    return f"{app_version}+g{github_sha[:7].lower()}"


def _read_source_version() -> str | None:
    """Return the version from pyproject.toml when running from a checkout."""
    module_path = Path(__file__).resolve()
    project_root = module_path.parents[1]
    # Only trust a pyproject.toml that sits right above this very package, not
    # whatever project an installed copy happens to be nested in
    if (project_root / PROJECT_NAME / module_path.name).resolve() != module_path:
        return None

    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.is_file():
        return None

    try:
        return read_project_version(pyproject_path)
    except InvalidVersion, ValueError:
        return None


def _read_installed_version() -> str | None:
    """Return the installed package's version."""
    try:
        return distribution_version(PROJECT_NAME)
    except PackageNotFoundError:
        return None


def read_version() -> str:
    """Return the running Lutris version."""
    return _read_source_version() or _read_installed_version() or UNKNOWN_VERSION


def _cli(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve Lutris build versions.")
    parser.add_argument("--artifact-version", metavar="VERSION", required=True)
    options = parser.parse_args(arguments)
    try:
        resolved_version = build_artifact_version(options.artifact_version)
    except (InvalidVersion, ValueError) as ex:
        parser.error(str(ex))
    print(resolved_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
