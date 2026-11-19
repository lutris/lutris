# Development shell for NixOS / Nix users. See "NixOS" in CONTRIBUTING.md.

{ pkgs ? import <nixpkgs> { } }:

let
  # Only the interpreter comes from Nix. Every Python package, PyGObject and
  # dbus-python included, is installed into .venv by `uv sync` from uv.lock,
  # built against the C libraries in buildInputs below.
  python = pkgs.python3;

  # Runs the checkout inside steam-run so downloaded runners (Wine, Proton...)
  # find their libraries. steam-run puts its own python3 first in PATH and
  # drops GIO_EXTRA_MODULES (no TLS without glib-networking), so pass both in.
  lutris-steam-run = pkgs.writeShellScriptBin "lutris-steam-run" ''
    exec steam-run env GIO_EXTRA_MODULES="$GIO_EXTRA_MODULES" "$(command -v python)" ./bin/lutris "$@"
  '';
in
pkgs.mkShell {
  nativeBuildInputs = with pkgs; [
    gobject-introspection # sets GI_TYPELIB_PATH from buildInputs
    wrapGAppsHook3
    # meson/ninja also build PyGObject, pycairo and dbus-python for uv; the
    # PyPI ninja binary can't run on NixOS (see NINJA below)
    meson
    ninja
    pkg-config
    gettext
    uv
  ];

  buildInputs = with pkgs; [
    python
    # headers for the Python packages uv builds from source
    glib
    cairo
    dbus
    lutris-steam-run
    gtk3
    webkitgtk_4_1
    libnotify
    gnome-desktop
    glib-networking
    gsettings-desktop-schemas
    file # libmagic, loaded via ctypes by lutris/util/magic.py
    # tools Lutris shells out to
    psmisc
    cabextract
    unzip
    p7zip
    curl
    xrandr
    mesa-demos
    vulkan-tools
    pciutils
  ];

  shellHook = ''
    # wrapGAppsHook only wraps binaries at build time; replicate its env here
    export XDG_DATA_DIRS="${pkgs.gsettings-desktop-schemas}/share/gsettings-schemas/${pkgs.gsettings-desktop-schemas.name}:${pkgs.gtk3}/share/gsettings-schemas/${pkgs.gtk3.name}:$XDG_DATA_DIRS"
    export GIO_EXTRA_MODULES="${pkgs.glib-networking}/lib/gio/modules''${GIO_EXTRA_MODULES:+:$GIO_EXTRA_MODULES}"
    export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath [ pkgs.file ]}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

    # nix-shell points these at a per-shell directory that the Proton/umu
    # container can't see, which breaks winetricks
    export TMPDIR=/tmp TMP=/tmp TEMP=/tmp TEMPDIR=/tmp

    # uv must use the Nix interpreter: its own downloaded Pythons expect an
    # FHS dynamic loader that NixOS doesn't have
    export UV_PYTHON="${python}/bin/python3" UV_PYTHON_DOWNLOADS=never
    # dbus-python's build pulls in the PyPI ninja anyway; this makes meson-python
    # run the Nix one instead
    export NINJA="${pkgs.ninja}/bin/ninja"
    # uv builds in isolated envs under ~/.cache; the Nix compiler wrapper would
    # otherwise drop their include paths (PyGObject needs pycairo's from there)
    export NIX_ENFORCE_PURITY=0
    # evdev's build only looks for linux/input.h in /usr/include and these
    export C_INCLUDE_PATH="${pkgs.linuxHeaders}/include''${C_INCLUDE_PATH:+:$C_INCLUDE_PATH}"
    uv sync
    source .venv/bin/activate
  '';
}
