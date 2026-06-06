#!/usr/bin/env bash
# Top-level wrapper for the Lutris AppImage proof-of-concept build.
#
# Builds (or reuses) the Docker image defined by ./Dockerfile, then runs
# the in-container build script with the repo mounted at /src. The
# finished AppImage lands in ./dist/.
#
# Usage:
#   utils/appimage/build.sh          # builds with version "dev"
#   LUTRIS_VERSION=0.5.23 utils/appimage/build.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE_TAG="lutris-appimage-builder:ubuntu22.04"

if command -v docker >/dev/null 2>&1; then
    OCI=docker
elif command -v podman >/dev/null 2>&1; then
    OCI=podman
else
    echo "docker or podman is required to build the AppImage" >&2
    exit 1
fi
echo "Using container engine: $OCI"

"$OCI" build -t "$IMAGE_TAG" "$SCRIPT_DIR"

mkdir -p "$REPO_ROOT/dist"

# --privileged lets appimagetool / linuxdeploy mount the squashfs they
# operate on; under podman with SELinux we also need :z on the bind mount.
MOUNT_OPTS=""
if [ "$OCI" = "podman" ]; then
    MOUNT_OPTS=":z"
fi

"$OCI" run --rm \
    --privileged \
    -v "$REPO_ROOT":/src${MOUNT_OPTS} \
    -e LUTRIS_VERSION="${LUTRIS_VERSION:-dev}" \
    "$IMAGE_TAG" \
    bash /src/utils/appimage/build-in-container.sh

echo
echo "Built AppImage(s):"
ls -lh "$REPO_ROOT/dist/"*.AppImage 2>/dev/null || echo "(no AppImage produced — check build output above)"
