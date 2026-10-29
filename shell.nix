# Development shell for NixOS / Nix users. See "NixOS" in CONTRIBUTING.md.

{ pkgs ? import <nixpkgs> { } }:

let
  python = pkgs.python3.withPackages (ps: with ps; [
    # runtime deps (pyproject.toml)
    pyyaml
    lxml
    requests
    pillow
    setproctitle
    python-magic
    distro
    dbus-python
    evdev
    pygobject3
    pycairo
    pypresence
    protobuf
    moddb
    # test runner; ruff/mypy are pinned by `make dev` and go in the venv
    nose2
    pip
  ]);

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
    meson
    ninja
    gettext
  ];

  buildInputs = with pkgs; [
    python
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

    # pinned ruff/mypy-baseline/pygobject-stubs from `make dev` go in a venv
    # that still sees the Nix-provided PyGObject
    if [ ! -d .venv ]; then
      python -m venv --system-site-packages .venv
    fi
    source .venv/bin/activate
  '';
}
