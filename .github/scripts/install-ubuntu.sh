#!/bin/bash -e
# Handles installing dependencies for the build process.  If an
# install-ubuntu-$OS_VERSION.sh script exists, install-ubuntu-22.04.sh
# for example, then that script is executed to install dependencies
# for that particular build instead of the install-ubuntu-generic.sh
# script.
#
# The following environment variables are optional and will override
# default values.
#
#   CODEBASE_ROOT
#       The absolute real path to the git repository root directory.
#
#   OS_CODENAME
#       The Ubuntu codename the package is being built for.
#       Ex. "jammy" or "kinetic"
#


# Go three directories up to get the codebase root path.
if [[ -z $CODEBASE_ROOT ]]; then
    CODEBASE_ROOT="$(dirname "$(dirname "$(dirname "$(readlink -f "$0")")")")"
fi

# This gets the Ubuntu codename & version from the local OS, or allows
# it to be passed in as an environment variable.
if [[ -z $OS_CODENAME ]]; then
    OS_CODENAME="$(grep 'VERSION_CODENAME=' /etc/os-release | cut -f2 -d'=' | tr -d '"')"
fi
if [[ -z $OS_VERSION ]]; then
    OS_VERSION="$(grep 'VERSION_ID=' /etc/os-release | cut -f2 -d'=' | tr -d '"')"
fi

# Runs a specific install script for an OS version if it exists or runs
# the generic install script.
if [[ -e "${CODEBASE_ROOT}/.github/scripts/install-ubuntu-${OS_VERSION}.sh" ]]; then
    echo "::group::Installing $OS_CODENAME ($OS_VERSION) build dependencies"
    # shellcheck disable=SC1090
    source "${CODEBASE_ROOT}/.github/scripts/install-ubuntu-${OS_VERSION}.sh"
else
    echo "::group::Installing generic build dependencies"
    # shellcheck source=./install-ubuntu-generic.sh
    source "${CODEBASE_ROOT}/.github/scripts/install-ubuntu-generic.sh"
fi
echo "::endgroup::"
