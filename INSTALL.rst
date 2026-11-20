Installing Lutris
=================

There are two supported ways to run Lutris: the Flatpak, built from this
repository, or straight from the source tree with `uv <https://docs.astral.sh/uv/>`_.

Flatpak
-------

The Flatpak bundles everything Lutris needs, including the 32-bit libraries,
tools and Wine base that games rely on. Its manifest lives in
``packaging/flatpak``. You need ``flatpak`` with the Flathub remote set up,
and ``flatpak-builder`` (either the distribution package or the
``org.flatpak.Builder`` app from Flathub)::

    git clone --recurse-submodules https://github.com/jedace07/lutris
    cd lutris
    make flatpak            # builds and installs it for the current user
    flatpak run net.lutris.Lutris

``make flatpak-bundle`` instead produces a single ``lutris.flatpak`` file that
can be installed elsewhere with ``flatpak install lutris.flatpak``. Every CI
build of ``master`` publishes that bundle as a workflow artifact, and every
release has it attached.

The first build takes a long time, as it compiles the bundled tools (Qt,
DOSBox Staging, Mono and others); later builds reuse flatpak-builder's cache.

The sandbox can read and write your home directory and any drive mounted under
``/mnt``, ``/media`` or ``/run/media``. Games elsewhere need an override, for
example ``flatpak override --user --filesystem=/srv/games net.lutris.Lutris``.

From source
-----------

uv installs Lutris's Python dependencies, at the versions pinned in
``uv.lock``, into a virtualenv in the checkout. The rest comes from your
distribution.

Build requirements, for the Python packages that compile against C libraries
(PyGObject, pycairo, dbus-python and evdev):

* Fedora: ``gcc pkgconf-pkg-config gobject-introspection-devel cairo-devel cairo-gobject-devel dbus-devel kernel-headers``
* Debian/Ubuntu: ``build-essential pkg-config libgirepository-2.0-dev libcairo2-dev libdbus-1-dev linux-libc-dev``
* Arch: ``base-devel gobject-introspection cairo dbus linux-api-headers``

Runtime requirements, the libraries Lutris loads through GObject introspection
and the tools it runs:

* Fedora: ``gtk3 webkit2gtk4.1 libnotify gnome-desktop3 glib-networking file-libs psmisc cabextract unzip 7zip curl xrandr mesa-demos vulkan-tools fluid-soundfont-gs``
* Debian/Ubuntu: ``gir1.2-gtk-3.0 gir1.2-webkit2-4.1 gir1.2-notify-0.7 gir1.2-gnomedesktop-3.0 glib-networking libmagic1 psmisc cabextract unzip p7zip-full curl x11-xserver-utils mesa-utils vulkan-tools fluid-soundfont-gs``
* Arch: ``gtk3 webkit2gtk-4.1 libnotify gnome-desktop glib-networking file psmisc cabextract unzip p7zip curl xorg-xrandr mesa-utils vulkan-tools soundfont-fluid``

GnomeDesktop is only used to read screen resolutions on Wayland, where xrandr
can't. To run games you'll also want the 32-bit OpenGL and Vulkan drivers for
your graphics card, and optionally Wine, gamemode and gamescope.

Then::

    git clone https://github.com/jedace07/lutris
    cd lutris
    uv sync --no-dev        # or `make dev` to include the development tools
    uv run bin/lutris

uv downloads its own build of Python 3.14 for this; your system's Python isn't
used, so it doesn't matter which version (if any) your distribution ships.
After pulling new changes, ``uv run`` brings the environment up to date by
itself.
