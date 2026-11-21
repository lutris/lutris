Installing Lutris
=================

There are two supported ways to run Lutris: the Flatpak, built from this
repository, or straight from the source tree with `uv <https://docs.astral.sh/uv/>`_.

Flatpak
-------

The Flatpak bundles everything Lutris needs, including the 32-bit libraries,
tools and Wine base that games rely on, on the freedesktop runtime. Its
manifest lives in ``packaging/flatpak``.

The simplest build is the one CI runs: a Fedora container with a current
``flatpak-builder``, so nothing but ``podman`` (or ``docker``) is needed on the
host, and nothing gets installed there::

    git clone --recurse-submodules https://github.com/jedace07/lutris
    cd lutris
    podman run --rm --privileged --security-opt label=disable -v "$PWD:/src" -w /src \
        registry.fedoraproject.org/fedora:45 \
        packaging/flatpak/container-build.sh packaging/flatpak/net.lutris.Lutris.yml lutris.flatpak
    flatpak install --user lutris.flatpak
    flatpak run net.lutris.Lutris

Add ``-v "$PWD/build-flatpak/flatpak:/var/lib/flatpak"`` to keep the downloaded
runtimes between builds.

To build on the host instead, use the ``org.flatpak.Builder`` app from Flathub
(older distribution packages of ``flatpak-builder`` can misplace libraries)::

    flatpak run org.flatpak.Builder --user --install --install-deps-from=flathub --force-clean \
        --state-dir=build-flatpak/state build-flatpak/build packaging/flatpak/net.lutris.Lutris.yml

Every CI build of ``main`` publishes a bundle, and every release has one
attached. The first build compiles bundled tools such as DOSBox Staging and
Mono. Later builds reuse flatpak-builder's cache.

The sandbox can read and write your home directory and any drive mounted under
``/mnt``, ``/media`` or ``/run/media``. Games elsewhere need an override, for
example ``flatpak override --user --filesystem=/srv/games net.lutris.Lutris``.

From source
-----------

uv installs Lutris and the Python dependencies pinned in ``uv.lock`` in a
virtualenv in the checkout. The rest comes from your distribution.

Build requirements, for the Python packages that compile against C libraries
(PyGObject, pycairo, dbus-python and evdev):

* Fedora: ``gcc pkgconf-pkg-config gobject-introspection-devel cairo-devel cairo-gobject-devel dbus-devel kernel-headers``
* Debian/Ubuntu: ``build-essential pkg-config libgirepository-2.0-dev libcairo2-dev libdbus-1-dev linux-libc-dev``
* Arch: ``base-devel gobject-introspection cairo dbus linux-api-headers``

Runtime requirements, the libraries Lutris loads through GObject introspection
and the tools it runs. The desktop application uses Qt Quick (PySide6 Essentials
from ``uv.lock``); it does not require GTK introspection packages:

* Fedora: ``glib-networking file-libs psmisc cabextract unzip 7zip curl xrandr mesa-demos vulkan-tools fluid-soundfont-gs``
* Debian/Ubuntu: ``glib-networking libmagic1 psmisc cabextract unzip p7zip-full curl x11-xserver-utils mesa-utils vulkan-tools fluid-soundfont-gs``
* Arch: ``glib-networking file psmisc cabextract unzip p7zip curl xorg-xrandr mesa-utils vulkan-tools soundfont-fluid``

On X11, Qt's ``xcb`` plugin also needs your distribution's XCB helper libraries,
including ``xcb-util-cursor`` (``libxcb-cursor0`` on Debian/Ubuntu).
To run games you'll also want the 32-bit OpenGL and Vulkan drivers for your
graphics card, and optionally Wine and gamescope. Bundled or separately
installed tools and games may still use GTK themselves.

Install GNU gettext if you want translations. After installing the system
dependencies, run::

    git clone https://github.com/jedace07/lutris
    cd lutris
    uv run lutris

uv downloads its own build of Python 3.14 for this; your system's Python isn't
used, so it doesn't matter which version (if any) your distribution ships.
After pulling new changes, ``uv run`` updates the environment. Use
``uv run --no-dev lutris`` to skip the development tools or ``uv build`` to
build a wheel and source distribution. The checkout's virtualenv does not
register Lutris in your desktop menu; use the Flatpak for desktop integration.
