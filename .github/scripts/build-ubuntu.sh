#!/bin/bash -e
# This script is intended to be run as part of a GitHub workflow where we
# build multiple times under different OS versions, which _may_ produce
# differences in the built packages.
#
# It expects the following environment variables:
#
#   PPA_GPG_PRIVATE_KEY
#       Private key with access to the Ubuntu PPA.  Note that if the
#       optional env variable PPA_GPG_KEY_ID is passed, then this
#       variable is not required.  If both are passed, then PPA_GPG_KEY_ID
#       is used.
#
#   PPA_GPG_PASSPHRASE
#       Decrypts the above private key or PPA_GPG_KEY_ID.
#
#   PPA_URI
#       The URI of the PPA to push updates to.
#       Ex. ppa:lutris-team/lutris
#
# The following environment variables are optional and will override
# default values.
#
#   CODEBASE_ROOT
#       The absolute real path to the git repository root directory.
#
#   LUTRIS_VERSION
#       The version of Lutris being built, in semver format.
#       Ex. "0.5.12-1" or "0.5.12"
#
#   OS_CODENAME
#       The Ubuntu codename the package is being built for.
#       Ex. "jammy" or "kinetic"
#
#   LUTRIS_DEBIAN_VERSION
#       The Debian-specific version which follows the guidelines
#       specified here: https://help.launchpad.net/Packaging/PPA/BuildingASourcePackage#Versioning
#       Ex. "0.5.12-0ubuntu1"
#
#   PPA_VERSION
#       The PPA release version which follows the same guide as mentioned
#       in the LUTRIS_DEBIAN_VERSION variable.
#       Ex. "ppa1~ubuntu22.04" or "ppa3~ubuntu22.04"
#
#   PPA_GPG_KEY_ID
#       The Full or Partial ID of a GPG Key that is imported into the GPG
#       key store.  This can be listed with `gpg --list-secret-keys`.
#       Ex.  7596C2FB25663E2B6DD9F97CF380C7EDED8F0491 (Full Key ID)
#       Ex.  F380C7EDED8F0491 (Partial Key ID)
#


# Go three directories up to get the codebase root path.
if [[ -z $CODEBASE_ROOT ]]; then
    CODEBASE_ROOT="$(dirname "$(dirname "$(dirname "$(readlink -f "$0")")")")"
fi

# This gets the Ubuntu codename & version from the local OS if they are
# not passed in to us already.
if [[ -z $OS_CODENAME ]]; then
    OS_CODENAME="$(grep 'VERSION_CODENAME=' /etc/os-release | cut -f2 -d'=' | tr -d '"')"
fi
# Get the OS version associated with OS_CODENAME.
OS_VERSION="$(distro-info --series "${OS_CODENAME}" -r | cut -f1 -d' ')"

# Get the base Lutris version in the same way that the Makefile does.
if [[ -z $LUTRIS_VERSION ]]; then
    LUTRIS_VERSION="$(grep "__version__" "${CODEBASE_ROOT}/lutris/__init__.py" | cut -d" " -f 3 | sed 's|"\(.*\)"|\1|')"
fi

# Creates a GPG keyring using the key passed from the GitHub workflow.
if [[ -z $PPA_GPG_KEY_ID ]]; then
    echo "::group::Importing GPG private key..."
    PPA_GPG_KEY_ID=$(echo "${PPA_GPG_PRIVATE_KEY}" | gpg --import-options show-only --import | sed -n '2s/^\s*//p')
    export PPA_GPG_KEY_ID
    echo "${PPA_GPG_KEY_ID}"
    echo "${PPA_GPG_PRIVATE_KEY}" | gpg --batch --passphrase "${PPA_GPG_PASSPHRASE}" --import
    echo "::endgroup::"

    # May as well since we don't need after at this point.
    unset PPA_GPG_PRIVATE_KEY
fi

# Add the ppa if it isn't already.
if ! grep -qi "${PPA_URI//ppa:/}" /etc/apt/sources.list.d/*.list; then
    sudo apt-add-repository -y "${PPA_URI}"
fi
# Get the current version of Lutris on the PPA.
if APT_VERSION="$(apt show lutris | grep 'Version: ' | cut -f2 -d' ')"; then
    echo "Latest version on '${PPA_URI}' is '${APT_VERSION}'"
else
    echo "Pushing first package to '${PPA_URI}'"
fi

# Version numbers are recommended to follow the guide at:
# https://help.launchpad.net/Packaging/PPA/BuildingASourcePackage#Versioning
#
# The basic format is:
# <lutris_version>-<lutris_revision>ubuntu<ubuntu_specific_revision>ppa<ppa_revision>~ubuntu<ubuntu_version>
#
# ex. 0.5.12-0ubuntu1 (for just the package version)
# ex. 0.5.12-0ubuntu1ppa1~ubuntu22.04 (for a package version meant for jammy)
# ex. 0.5.12-0ubuntu1ppa1~ubuntu20.04 (for a package version meant for focal)
# etc...
#
PPA_VERSION="ppa1~ubuntu${OS_VERSION}"

# If the Lutris version doesn't have a revision, we add revision 0.
LUTRIS_DEBIAN_VERSION="${LUTRIS_VERSION}"
if [[ "${LUTRIS_VERSION}" = "${LUTRIS_VERSION/-*/}" ]]; then
    LUTRIS_DEBIAN_VERSION="${LUTRIS_DEBIAN_VERSION}-0"
fi

# Finally, add an ubuntu revision, so that other packages can override ours
# without bumping the actual version number.
LUTRIS_DEBIAN_VERSION="${LUTRIS_DEBIAN_VERSION}ubuntu1"

# If the version we're currently building exists on the PPA, increment
# the PPA version number so that we supersede it.  Assuming a version
# scheme like 0.5.12-0ubuntu1ppa1~ubuntu22.04, we trim everything up to
# and including 'ppa' and everything after and including '~' to get the
# PPA version number.
if [[ "${APT_VERSION//ppa*/}" = "${LUTRIS_DEBIAN_VERSION}" ]]; then
    echo "PPA (${PPA_URI}) has matching package version: ${LUTRIS_DEBIAN_VERSION}"
    APT_PPA_VERSION="${APT_VERSION//*ppa/}"
    APT_PPA_VERSION="${APT_PPA_VERSION//~*/}"
    # Only autoincrement if the derived APT_PPA_VERSION is an integer.
    if [[ ${APT_PPA_VERSION} =~ ^[0-9]*$ ]]; then
        (( APT_PPA_VERSION++ ))
        PPA_VERSION="ppa${APT_PPA_VERSION}~ubuntu${OS_VERSION}"
    else
        echo "Could not derive APT_PPA_VERSION from '${APT_VERSION}'; using default."
    fi
fi

# Runs a specific build script for an OS Version if it exists or runs
# the generic build script if not.  GitHub seems to only support LTS
# versions of Ubuntu runners for build jobs, and so we use this to
# build the non-LTS versions on the closest matching LTS version.
if [[ -f "${CODEBASE_ROOT}/.github/scripts/build-ubuntu-${OS_VERSION}.sh" ]]; then
    echo "::group::Building version-specific deb for ${OS_CODENAME}: ${LUTRIS_DEBIAN_VERSION}${PPA_VERSION}"
    # shellcheck disable=SC1090
    source "${CODEBASE_ROOT}/.github/scripts/build-ubuntu-${OS_VERSION}.sh"
else
    echo "::group::Building generic deb for ${OS_CODENAME}: ${LUTRIS_DEBIAN_VERSION}${PPA_VERSION}"
    # shellcheck source=./build-ubuntu-generic.sh
    source "${CODEBASE_ROOT}/.github/scripts/build-ubuntu-generic.sh"
fi
echo "::endgroup::"
