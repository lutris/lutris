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
import sys

from setuptools import setup

if sys.version_info < (3, 10):
    sys.exit("Python >= 3.10 is required to run Lutris")

data_files = []

for directory, _, filenames in os.walk("share"):
    dest = directory[6:]
    if filenames:
        files = [os.path.join(directory, filename) for filename in filenames]
        data_files.append((os.path.join("share", dest), files))

setup(data_files=data_files)
