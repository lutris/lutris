#!/usr/bin/env bash
# Assemble the Lutris AppDir and produce an AppImage.
#
# This runs inside the Docker image defined by Dockerfile. It expects the
# Lutris source tree to be mounted at /src, and writes the finished
# AppImage to /src/dist/.
set -euo pipefail

SRC=/src
OUT=$SRC/dist
APPDIR=/tmp/Lutris.AppDir

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib" "$OUT"

# Bundle the Python interpreter + standard library so the AppImage doesn't
# depend on the host having python3.10 installed. We use whatever python3
# the build image ships (Ubuntu 22.04 → 3.10).
PY_VER="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
cp -a "$(readlink -f /usr/bin/python3)" "$APPDIR/usr/bin/python${PY_VER}"
ln -sf "python${PY_VER}" "$APPDIR/usr/bin/python3"
cp -a "/usr/lib/python${PY_VER}" "$APPDIR/usr/lib/"
# Drop test/idle bloat that no end user needs from the AppImage. The
# config-* directory holds link-time-only artifacts (Makefile, python.o
# static wrapper, libpython symlinks) that are useful only when building
# C extensions against this Python — never at runtime — and the python.o
# in it makes linuxdeploy emit a spurious "patchelf: wrong ELF type"
# warning every build because it's a relocatable object file, which
# patchelf refuses to touch.
rm -rf "$APPDIR/usr/lib/python${PY_VER}/test" \
       "$APPDIR/usr/lib/python${PY_VER}/idlelib" \
       "$APPDIR/usr/lib/python${PY_VER}/turtledemo" \
       "$APPDIR/usr/lib/python${PY_VER}/tkinter" \
       "$APPDIR/usr/lib/python${PY_VER}/lib2to3" \
       "$APPDIR/usr/lib/python${PY_VER}/config-"*

# Install Lutris (Python package + bin/lutris + data files) into the AppDir.
cd "$SRC"
python3 setup.py install --root="$APPDIR" --prefix=/usr --no-compile

# Install runtime Python deps directly into the AppDir's site-packages.
SITE_PACKAGES=$(python3 -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
SITE_PACKAGES=${SITE_PACKAGES#/usr/}
TARGET="$APPDIR/usr/$SITE_PACKAGES"
mkdir -p "$TARGET"

# PyGObject is satisfied by the system python3-gi we bundle from apt; pip
# rebuilds against the host gobject-introspection and we want the version
# wired up to the bundled typelibs, so we leave it to apt + linuxdeploy.
# dbus-python is intentionally excluded here — it switched to a meson-python
# build backend that pulls in a heavy toolchain, and the apt-shipped
# python3-dbus is a perfectly good prebuilt copy we already have.
python3 -m pip install --no-compile --target="$TARGET" \
    certifi \
    distro \
    evdev \
    lxml \
    pillow \
    pypresence \
    PyYAML \
    requests \
    protobuf \
    'moddb>=0.8.1' \
    setproctitle

# Bundle the python3-gi / python3-dbus packages shipped by apt: their .so
# extensions live outside the pip world, and we want PyGObject/dbus wired
# up to the bundled typelibs and libdbus, not whatever the host has.
for path in /usr/lib/python3/dist-packages/gi \
            /usr/lib/python3/dist-packages/cairo \
            /usr/lib/python3/dist-packages/dbus \
            /usr/lib/python3/dist-packages/_dbus_bindings*.so \
            /usr/lib/python3/dist-packages/_dbus_glib_bindings*.so; do
    if compgen -G "$path" >/dev/null; then
        cp -a $path "$TARGET/"
    fi
done

# Stage desktop file + icon for linuxdeploy. It looks for them at the AppDir
# root, so symlink from the canonical install locations.
DESKTOP_FILE="$APPDIR/usr/share/applications/net.lutris.Lutris.desktop"
ICON_FILE="$APPDIR/usr/share/icons/hicolor/scalable/apps/net.lutris.Lutris.svg"
[ -f "$DESKTOP_FILE" ] || { echo "missing desktop file at $DESKTOP_FILE"; exit 1; }
[ -f "$ICON_FILE" ]    || { echo "missing icon at $ICON_FILE"; exit 1; }

# Drop in our custom AppRun before linuxdeploy runs, so it doesn't overwrite
# it with its own generic launcher.
install -m 0755 "$SRC/utils/appimage/AppRun" "$APPDIR/AppRun"

# Run linuxdeploy with the gtk plugin to copy GTK libs/typelibs/loaders.
# DEPLOY_GTK_VERSION tells the plugin which GTK major version to bundle.
export DEPLOY_GTK_VERSION=3
export LINUXDEPLOY_OUTPUT_VERSION=${LUTRIS_VERSION:-dev}

# --executable on the bundled python3 lets linuxdeploy walk its NEEDED list
# and copy in libpython, libssl, libffi, etc. that the interpreter pulls.
#
# --library on each native Python extension (.so) we copied in from
# apt's python3-gi / python3-dbus packages tells linuxdeploy to follow
# their NEEDED chain too. Without this, libgirepository / libdbus /
# libgobject never land in the AppDir, and ld.so falls back to the host
# copies — which on a newer distro than the build base will be ABI-
# incompatible with our bundled libglib.
LIB_ARGS=()
while IFS= read -r -d '' so; do
    LIB_ARGS+=(--library "$so")
done < <(find "$TARGET" -maxdepth 3 \( -name '_gi*.so' -o -name '_dbus*.so' -o -name 'gi.repository*.so' \) -print0 2>/dev/null)
echo "Passing ${#LIB_ARGS[@]} native extensions to linuxdeploy: ${LIB_ARGS[*]}"

linuxdeploy \
    --appdir "$APPDIR" \
    --plugin gtk \
    --executable "$APPDIR/usr/bin/python${PY_VER}" \
    "${LIB_ARGS[@]}" \
    --desktop-file "$DESKTOP_FILE" \
    --icon-file "$ICON_FILE"

# linuxdeploy writes its own AppRun; restore ours (which knows to exec
# python3 with bin/lutris and to source linuxdeploy-plugin-gtk's hook).
install -m 0755 "$SRC/utils/appimage/AppRun" "$APPDIR/AppRun"

# linuxdeploy patched RPATH on every binary it deployed itself, but it did
# not touch the files we copied in by hand (_gi.so, _dbus*.so under
# dist-packages). Since AppRun deliberately leaves LD_LIBRARY_PATH unset
# to avoid poisoning host subprocesses, those files would fall through to
# the host's libs at runtime — exactly the ABI mismatch we're trying to
# avoid. Stamp them with an $ORIGIN-relative RPATH pointing at the bundled
# $APPDIR/usr/lib so they pick up our libgirepository / libdbus / libglib.
LIB_DIR="$APPDIR/usr/lib"
while IFS= read -r -d '' so; do
    rel="$(realpath --relative-to="$(dirname "$so")" "$LIB_DIR")"
    patchelf --set-rpath "\$ORIGIN/$rel" "$so"
    echo "  rpath \$ORIGIN/$rel -> $so"
done < <(find "$TARGET" -maxdepth 3 \( -name '_gi*.so' -o -name '_dbus*.so' \) -print0 2>/dev/null)

# Finally, pack the AppDir into a single-file AppImage.
cd "$OUT"
ARCH=x86_64 appimagetool --no-appstream "$APPDIR" \
    "Lutris-${LINUXDEPLOY_OUTPUT_VERSION}-x86_64.AppImage"

ls -lh "$OUT"
