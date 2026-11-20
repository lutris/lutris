#!/bin/bash
# Build the Flatpak inside a Fedora container, the way CI does, so local builds
# match it and nothing is installed on the host. From the repository root:
#
#   podman run --rm --privileged --security-opt label=disable -v "$PWD:/src" -w /src \
#       registry.fedoraproject.org/fedora:45 packaging/flatpak/container-build.sh
#
# Arguments: the manifest (net.lutris.Lutris.yml by default), and a bundle file to
# write once it's built. Output goes under build-flatpak/, which git ignores. Set
# OWNER (uid:gid) to hand that output back to the host user afterwards.
set -euo pipefail

manifest=${1:-packaging/flatpak/net.lutris.Lutris.yml}
bundle=${2:-}

# flatpak-builder applies patches and unpacks some archives with the host's tools
dnf install -y --setopt=install_weak_deps=False flatpak flatpak-builder git-core patch tar bzip2 xz unzip
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak-builder --version

status=0
flatpak-builder --install-deps-from=flathub --disable-rofiles-fuse --force-clean \
    --state-dir=build-flatpak/state --repo=build-flatpak/repo \
    build-flatpak/build "$manifest" || status=$?

if [ "$status" -eq 0 ] && [ -n "$bundle" ]; then
    flatpak build-bundle build-flatpak/repo "$bundle" net.lutris.Lutris \
        --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo || status=$?
fi

# Even after a failure, so CI can still cache the modules that did build
if [ -n "${OWNER:-}" ]; then
    chown -R "$OWNER" build-flatpak ${bundle:+"$bundle"} 2>/dev/null || true
fi
exit "$status"
