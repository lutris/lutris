#!/bin/bash
# Install a built bundle in a throwaway Fedora container and check that Lutris
# works in it, as a regular user (Lutris refuses to run as root). From the
# repository root:
#
#   podman run --rm --privileged --security-opt label=disable -v "$PWD:/src" -w /src \
#       registry.fedoraproject.org/fedora:45 packaging/flatpak/smoke-test.sh lutris.flatpak
set -euo pipefail

bundle=$1

dnf install -y --setopt=install_weak_deps=False flatpak dbus-daemon util-linux
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install -y --noninteractive --reinstall --bundle "$bundle"

useradd -m player
runtime_dir=$(mktemp -d)
chown player "$runtime_dir"
chmod 700 "$runtime_dir"
as_player() {
    runuser -u player -- env XDG_RUNTIME_DIR="$runtime_dir" dbus-run-session -- "$@"
}

echo "== Version"
as_player flatpak run net.lutris.Lutris --version

echo "== Python and Qt"
as_player flatpak run --command=python3 net.lutris.Lutris -c '
import sys, PySide6, gi
from PySide6 import QtQuick, QtQuickControls2
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib
import lutris.qt.main_window
print(sys.version.split()[0], PySide6.__version__, gi.__version__)
'

echo "== Bundled tools"
as_player flatpak run --command=sh net.lutris.Lutris -c '
for tool in wine winetricks dosbox retroarch glxinfo vulkaninfo xrandr fuser zenity java mono; do
    command -v "$tool" >/dev/null || { echo "missing: $tool"; exit 1; }
done
retroarch --version
echo "all present"
'

echo "== Window"
# Offscreen, the window should still be up after the timeout, with nothing failing to load
log=$(mktemp)
status=0
as_player timeout 30 flatpak run --env=QT_QPA_PLATFORM=offscreen net.lutris.Lutris >"$log" 2>&1 || status=$?
cat "$log"
if [ "$status" -ne 124 ]; then
    echo "Lutris exited early, with status $status"
    exit 1
fi
if grep -E "Traceback|QQmlApplicationEngine failed|is not a type|ReferenceError|TypeError" "$log"; then
    echo "Lutris reported errors while starting"
    exit 1
fi
echo "Lutris started and kept running"
