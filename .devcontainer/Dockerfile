FROM mcr.microsoft.com/devcontainers/universal:2-linux

# Lutris needs the GObject introspection (GI) bindings and the GTK/WebKit
# typelibs to import the `gi` module and build the C extension dependencies
# (PyGObject, pycairo, dbus-python). Install everything here so the image
# works out of the box and tests/builds run without extra setup.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-gi \
        python3-dbus \
        python3-gi-cairo \
        python3-venv \
        libgirepository-2.0-dev \
        gir1.2-gtk-3.0 \
        gir1.2-webkit2-4.1 \
        libgnome-desktop-3-dev \
        libcairo2-dev \
        libgtk-3-dev \
        libgdk-pixbuf-2.0-dev \
        libdbus-1-dev \
        libdbus-glib-1-dev \
        pkg-config \
        gettext \
    && rm -rf /var/lib/apt/lists/*
