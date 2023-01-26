#!/bin/bash
# This script is intended to be run as part of a GitHub workflow.  This specific
# script overrides the build generic build process for Ubuntu 22.04 (Jammy) and
# helps us work around the lack of GitHub Workflow Runners for non-LTS versions
# of Ubuntu.
#
# Required Environment Variables:
#
#   CODEBASE_ROOT
#       The absolute real path to the git repository root directory.
#
# Optional Environment Variables:
#
#   JAMMY_BUILDS
#       A space or new-line separated list of Ubuntu codenames.
#

# First run the standard build process for Jammy.
# shellcheck source=./build-ubuntu-generic.sh
source "${CODEBASE_ROOT}/.github/scripts/build-ubuntu-generic.sh"
echo "::endgroup::"

# Rerun the build process for all codenames in the JAMMY_BUILDS env
# variable.  We override the OS_CODENAME env variable, and then recurse
# into the ./build-ubuntu.sh build script to build those versions within
# our Jammy runner.
if [[ -n ${JAMMY_BUILDS} ]]; then
    for OS_CODENAME in ${JAMMY_BUILDS}; do
        if ! distro-info --series "${OS_CODENAME}"; then
            echo "Bad JAMMY_BUILDS codename '${OS_CODENAME}' provided.  Skipping this build."
        else
            # Clean up the codebase between runs.
            git reset --hard
            git clean -df
            # shellcheck source=./build-ubuntu.sh
            source "${CODEBASE_ROOT}/.github/scripts/build-ubuntu.sh"
        fi
    done
fi
