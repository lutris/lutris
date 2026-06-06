# Build environment for the Lutris AppImage proof-of-concept.
#
# Ubuntu 22.04 is chosen as a balance between glibc backward compatibility
# (glibc 2.35) and shipping Python 3.10 + GTK3 + WebKit2GTK 4.1 in the
# distro repos. If we promote this from PoC to a supported channel, we
# may want to drop to 20.04 (glibc 2.31) for wider portability.
FROM ubuntu:22.04

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
    libfuse2 \
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
    libcairo2-dev \
    libgirepository1.0-dev \
    libdbus-1-dev \
    libsystemd-dev \
    python3-gi \
    python3-gi-cairo \
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
    libgnome-desktop-3-19 \
    librsvg2-common \
 && rm -rf /var/lib/apt/lists/*

# linuxdeploy + plugin-gtk handle library/typelib bundling and GTK env setup.
WORKDIR /opt/tools
RUN curl -fsSL -o linuxdeploy-x86_64.AppImage \
    https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage \
 && curl -fsSL -o linuxdeploy-plugin-gtk.sh \
    https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gtk/master/linuxdeploy-plugin-gtk.sh \
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
