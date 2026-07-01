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
# depend on the host having a matching python3.X installed. We use whatever
# python3 the build image ships (Ubuntu 24.04 → 3.12).
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
# --install-layout=deb is Debian's flag for "use dist-packages, not the
# upstream-Python site-packages layout." This matters because the bundled
# Python is Debian-patched (Ubuntu 24.04) and its default sys.path looks
# for modules in dist-packages, not site-packages. Installing here means
# AppRun does not need to advertise our location on PYTHONPATH, which in
# turn keeps PYTHONPATH out of host subprocesses (umu-run's #!/usr/bin/env
# python3 picks up the host interpreter, with its host site-packages).
cd "$SRC"
python3 setup.py install --root="$APPDIR" --prefix=/usr --install-layout=deb --no-compile

# Install runtime Python deps directly into the AppDir's site-packages.
SITE_PACKAGES=$(python3 -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
SITE_PACKAGES=${SITE_PACKAGES#/usr/}
TARGET="$APPDIR/usr/$SITE_PACKAGES"
mkdir -p "$TARGET"

# PyGObject is satisfied by the system python3-gi we bundle from apt; pip
# rebuilds against the host gobject-introspection and we want the version
# wired up to the bundled typelibs, so we leave it to apt + linuxdeploy.
# PyGObject and dbus-python both ship as source-only distributions and
# build via meson-python — that's why the Dockerfile pulls in meson +
# ninja-build + libdbus-glib-1-dev. Building them through pip (rather
# than copying apt's python3-gi / python3-dbus into the AppDir by hand)
# keeps every runtime dep on a single, version-pinnable surface and
# lets pycairo land naturally as a PyGObject dependency.
#
# --break-system-packages opts past Noble's PEP 668 guard; safe because
# --target installs to the AppDir, not the system Python.
python3 -m pip install --no-compile --break-system-packages --target="$TARGET" \
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
    setproctitle \
    pycairo \
    'PyGObject<3.50' \
    dbus-python

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
export DEPLOY_GTK_VERSION=4
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

# WebKitGTK is loaded lazily via gi.repository (only when the user opens a
# service login dialog), so it never appears in any binary's NEEDED list
# at build time. Without explicit --library hints linuxdeploy doesn't
# bundle libwebkitgtk-6.0 or libjavascriptcoregtk-6.0, and at runtime
# dlopen() falls through to the host copies — typically older than ours,
# causing missing-symbol errors like webkit_network_session_new. Pass
# both sonames explicitly so linuxdeploy follows their NEEDED chains.
WEBKIT_LIB_ARGS=()
for soname in libwebkitgtk-6.0.so.4 libjavascriptcoregtk-6.0.so.1; do
    so_path="$(ldconfig -p | awk -v n="$soname" '$1 == n { print $NF; exit }')"
    if [ -n "$so_path" ] && [ -f "$so_path" ]; then
        WEBKIT_LIB_ARGS+=(--library "$so_path")
    else
        echo "WARNING: $soname not found via ldconfig — WebKit dialogs will use host libs"
    fi
done
echo "Passing ${#WEBKIT_LIB_ARGS[@]} WebKit libraries to linuxdeploy: ${WEBKIT_LIB_ARGS[*]}"

linuxdeploy \
    --appdir "$APPDIR" \
    --plugin gtk \
    --executable "$APPDIR/usr/bin/python${PY_VER}" \
    "${LIB_ARGS[@]}" \
    "${WEBKIT_LIB_ARGS[@]}" \
    --desktop-file "$DESKTOP_FILE" \
    --icon-file "$ICON_FILE"

# linuxdeploy writes its own AppRun; restore ours (which knows to exec
# python3 with bin/lutris and to source linuxdeploy-plugin-gtk's hook).
install -m 0755 "$SRC/utils/appimage/AppRun" "$APPDIR/AppRun"

# linuxdeploy-plugin-gtk copies libgio itself but not the GIO modules that
# live at $gio_libdir/gio/modules/ — these include glib-networking's
# libgiognutls.so, which provides GLib's TLS backend. Without it, WebKit
# reports "TLS is not available" the moment it tries to open an HTTPS URL.
# On Debian/Ubuntu hosts we happen to fall through to the host's copy at
# the same path, but on Fedora/Arch/openSUSE the compile-time fallback
# path doesn't exist and TLS silently breaks. Copy the whole modules
# directory and let AppRun set GIO_MODULE_DIR.
GIO_MODULES_SRC="/usr/lib/x86_64-linux-gnu/gio/modules"
GIO_MODULES_DST="$APPDIR/usr/lib/gio/modules"
if [ -d "$GIO_MODULES_SRC" ]; then
    echo "Copying GIO modules from $GIO_MODULES_SRC"
    mkdir -p "$GIO_MODULES_DST"
    cp -a "$GIO_MODULES_SRC"/. "$GIO_MODULES_DST/"
    # RPATH each .so at $ORIGIN/../.. so its NEEDED libs resolve back to
    # $APPDIR/usr/lib. Without this, libgiognutls falls through to the
    # host's libgnutls / libp11-kit which may have incompatible ABIs.
    while IFS= read -r -d '' so; do
        patchelf --set-rpath '$ORIGIN/../..' "$so" 2>/dev/null || true
        echo "  rpath \$ORIGIN/../.. -> $so"
    done < <(find "$GIO_MODULES_DST" -name '*.so' -print0)
else
    echo "WARNING: $GIO_MODULES_SRC not present — WebKit TLS will not work"
fi

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

# WebKitGTK 6.0 forks helper processes (WebKitNetworkProcess,
# WebKitWebProcess) that live in /usr/lib/x86_64-linux-gnu/webkitgtk-6.0/.
# linuxdeploy bundles shared libraries but not auxiliary executables, so
# without copying this directory by hand the bundled libwebkitgtk-6.0
# tries to spawn an absent /usr/lib/.../WebKitNetworkProcess and fatally
# aborts. Place the dir inside the AppDir and patch RPATHs so the
# processes find our bundled libwebkitgtk via $ORIGIN/..
#
# WebKitGTK 6.0 dropped the WEBKIT_EXEC_PATH env override that older
# versions honored — the helper-process directory is now baked in at
# compile time with no runtime hook. Work around this by patching the
# hardcoded path inside libwebkitgtk-6.0.so.4 to a writable
# /tmp/.lutris-appimage.dir/webkitgtk-6.0 location (exactly the same
# byte length as the original so .rodata layout stays intact), and have
# AppRun create that path as a symlink to the bundled directory at
# startup. The injected-bundle path uses the same prefix so the byte
# replacement updates both strings in one pass.
WEBKIT_SRC_DIR="/usr/lib/x86_64-linux-gnu/webkitgtk-6.0"
WEBKIT_DST_DIR="$APPDIR/usr/lib/webkitgtk-6.0"
WEBKIT_LIB="$APPDIR/usr/lib/libwebkitgtk-6.0.so.4"
WEBKIT_HARDCODED_PATH="/usr/lib/x86_64-linux-gnu/webkitgtk-6.0"
WEBKIT_PATCHED_PATH="/tmp/.lutris-appimage.dir/webkitgtk-6.0"
if [ -d "$WEBKIT_SRC_DIR" ]; then
    echo "Copying WebKitGTK auxiliary processes from $WEBKIT_SRC_DIR"
    mkdir -p "$WEBKIT_DST_DIR"
    cp -a "$WEBKIT_SRC_DIR"/. "$WEBKIT_DST_DIR/"
    while IFS= read -r -d '' elf; do
        if file "$elf" | grep -q "ELF.*executable\|ELF.*shared object"; then
            patchelf --set-rpath '$ORIGIN/..' "$elf" 2>/dev/null || true
            echo "  rpath \$ORIGIN/.. -> $elf"
        fi
    done < <(find "$WEBKIT_DST_DIR" -type f -print0)

    if [ -f "$WEBKIT_LIB" ]; then
        python3 - "$WEBKIT_LIB" "$WEBKIT_HARDCODED_PATH" "$WEBKIT_PATCHED_PATH" <<'PY'
import sys
path, old, new = sys.argv[1], sys.argv[2].encode(), sys.argv[3].encode()
assert len(old) == len(new), f"length mismatch: {len(old)} != {len(new)}"
data = open(path, 'rb').read()
count = data.count(old)
if count == 0:
    sys.exit(f"FATAL: hardcoded WebKit path {old!r} not found in {path}")
open(path, 'wb').write(data.replace(old, new))
print(f"Patched {count} occurrence(s) of {old.decode()} -> {new.decode()} in {path}")
PY
    fi
else
    echo "WARNING: $WEBKIT_SRC_DIR not present — WebKit dialogs will fail at runtime"
fi

# Finally, pack the AppDir into a single-file AppImage.
cd "$OUT"
ARCH=x86_64 appimagetool --no-appstream "$APPDIR" \
    "Lutris-${LINUXDEPLOY_OUTPUT_VERSION}-x86_64.AppImage"

ls -lh "$OUT"
