#!/usr/bin/env bash
set -euo pipefail

# Use the system Python (which has gi/dbus/cairo via apt) and a venv that
# sees those system packages, so C extensions don't need to be built against
# a static libpython.
python3 -m venv --system-site-packages /workspaces/lutris/.venv
/workspaces/lutris/.venv/bin/pip install --upgrade pip

# Runtime and development dependencies.
/workspaces/lutris/.venv/bin/pip install \
    PyYAML lxml requests Pillow setproctitle python-magic distro \
    types-requests types-PyYAML evdev pypresence protobuf moddb

/workspaces/lutris/.venv/bin/pip install \
    "ruff==0.12.1" "mypy==1.16.1" mypy-baseline nose2

/workspaces/lutris/.venv/bin/pip install \
    "pygobject-stubs>=2.17.0" --no-cache-dir --config-settings=config=Gtk3,Gdk3,Soup2

echo "Lutris devcontainer ready. Use /workspaces/lutris/.venv/bin/python"
