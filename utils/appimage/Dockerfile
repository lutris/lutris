# Build environment for the Lutris AppImage.
#
# Ubuntu 24.04 LTS (Noble) ships a newer point release of WebKitGTK 4.1
# (2.44+) than Jammy (2.42), fixing a bug where the bundled 22.04 WebKit
# renderer would silently die after one input event on some login pages
# (HumbleBundle, ZOOM). glibc floor moves to 2.39, so the AppImage
# stops running on hosts older than roughly 2024 distros — the
# documented trade-off.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    file \
    git \
    desktop-file-utils \
    gettext \
    appstream \
    libfuse2t64 \
    fuse \
    patchelf \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    python3-setuptools \
    python3-wheel \
    pkg-config \
    build-essential \
    meson \
    ninja-build \
    libcairo2-dev \
    libgirepository1.0-dev \
    libdbus-1-dev \
    libdbus-glib-1-dev \
    libsystemd-dev \
    python3-gi \
    python3-dbus \
    gir1.2-gtk-3.0 \
    gir1.2-gdkpixbuf-2.0 \
    gir1.2-pango-1.0 \
    gir1.2-gnomedesktop-3.0 \
    gir1.2-webkit2-4.1 \
    gir1.2-notify-0.7 \
    gir1.2-ayatanaappindicator3-0.1 \
    libgtk-3-0 \
    libgtk-3-bin \
    libwebkit2gtk-4.1-0 \
    libnotify4 \
    libayatana-appindicator3-1 \
    libgnome-desktop-3-20t64 \
    glib-networking \
    adwaita-icon-theme \
    librsvg2-common \
 && rm -rf /var/lib/apt/lists/*

# Two pip installs into the build image's system Python:
#   * pycairo, so PyGObject's meson build can find its C headers (apt's
#     python3-cairo ships no headers, which is why python3-cairo /
#     python3-gi-cairo are deliberately not in the apt list above).
#   * setuptools >=77, which is where PEP 639 SPDX string license
#     support landed. Lutris's pyproject.toml declares
#     `license = "GPL-3.0-or-later"` in that form, and Noble's apt
#     setuptools (68.1.2) rejects it at `setup.py install` time with
#     `configuration error: project.license must be valid exactly by
#     one definition`.
# PEP 668 makes Noble's system Python externally managed, so use
# --break-system-packages — safe because this image is single-purpose
# and the packages are consumed by the same Python.
RUN python3 -m pip install --no-cache-dir --break-system-packages \
    --ignore-installed packaging \
    'setuptools>=77' \
    'packaging>=24.2' \
    pycairo

# linuxdeploy + plugin-gtk handle library/typelib bundling and GTK env setup.
# linuxdeploy-plugin-gtk is vendored from the repo (see the matching
# .sh and .LICENSE files in this directory) because its upstream is
# dormant; pinning a known-good copy keeps builds reproducible and lets
# us patch known issues (e.g. forced Adwaita theme) without a fork.
WORKDIR /opt/tools
COPY linuxdeploy-plugin-gtk.sh /opt/tools/linuxdeploy-plugin-gtk.sh
RUN curl -fsSL -o linuxdeploy-x86_64.AppImage \
    https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage \
 && curl -fsSL -o appimagetool-x86_64.AppImage \
    https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage \
 && chmod +x linuxdeploy-x86_64.AppImage linuxdeploy-plugin-gtk.sh appimagetool-x86_64.AppImage

# linuxdeploy and appimagetool are AppImages; extract them so they run
# without FUSE (which isn't always usable inside containers).
RUN ./linuxdeploy-x86_64.AppImage --appimage-extract >/dev/null \
 && mv squashfs-root linuxdeploy \
 && ln -sf /opt/tools/linuxdeploy/AppRun /usr/local/bin/linuxdeploy \
 && ./appimagetool-x86_64.AppImage --appimage-extract >/dev/null \
 && mv squashfs-root appimagetool \
 && ln -sf /opt/tools/appimagetool/AppRun /usr/local/bin/appimagetool \
 && ln -sf /opt/tools/linuxdeploy-plugin-gtk.sh /usr/local/bin/linuxdeploy-plugin-gtk

WORKDIR /src
