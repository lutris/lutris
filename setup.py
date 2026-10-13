#!/usr/bin/env python3
"""Thin build shim for setuptools.

All Python packaging metadata (name, version, dependencies, entry-point
script, package list) now lives in ``pyproject.toml``.  Only the ``share/``
data files are still walked here, because setuptools cannot declare a whole
directory tree as ``data_files`` from ``pyproject.toml``.

This file is intentionally minimal but is still required: the AppImage build
(``utils/appimage/build-in-container.sh``) and the RPM spec (``packaging/
lutris.spec``) both install through ``setup.py``.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import cast

from setuptools import setup
from setuptools.command.build_py import build_py

if sys.version_info < (3, 10):
    sys.exit("Python >= 3.10 is required to run Lutris")

data_files = []

for directory, _, filenames in os.walk("share"):
    dest = directory[6:]
    if filenames:
        files = [os.path.join(directory, filename) for filename in filenames]
        data_files.append((os.path.join("share", dest), files))


class BuildPyWithCommit(build_py):  # type: ignore[misc]  # setuptools does not provide these stubs.
    """Include build provenance alongside the installed Python modules."""

    def run(self) -> None:
        super().run()
        revision = subprocess.check_output(
            [sys.executable, str(Path(__file__).parent / "utils/get-build-commit.py")], text=True
        ).strip()
        target = Path(self.build_lib) / "lutris/build_commit.txt"
        target.write_text(revision + "\n", encoding="ascii")

    def get_outputs(self, include_bytecode: int = 1) -> list[str]:
        outputs = cast(list[str], super().get_outputs(include_bytecode))
        return outputs + [str(Path(self.build_lib) / "lutris/build_commit.txt")]


setup(data_files=data_files, cmdclass={"build_py": BuildPyWithCommit})
