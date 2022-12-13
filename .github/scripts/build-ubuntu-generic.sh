#!/bin/bash
# Default build script for producing a generic Lutris build.
# It requires several environment variables which are typically
# passed in from the ./build-ubuntu.sh script.
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
#   PPA_GPG_PASSPHRASE
#       The passphrase to unlock the above PPA_GPG_KEY_ID.
#

# Make sure the changelog has a proper entry for the version being built.
if ! grep -q "${LUTRIS_VERSION}" "${CODEBASE_ROOT}/debian/changelog"; then
    echo "Error: ${CODEBASE_ROOT}/debian/changelog does not contain an entry for our current version."
    exit 255
fi

# Does an initial make process for creating a debian source package.
debmake -n -p lutris -u "${LUTRIS_VERSION}" -b":python3"

# Updates debian/control file based on current environment.
sudo mk-build-deps --install \
    --tool='apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes' \
    "${CODEBASE_ROOT}/debian/control"

# Update the changelog entry. Specifically we change the top most
# changelog entry codename to match our current OS and the version
# number to match the Debian+PPA version scheme described above.
sed -i"" \
    -re"1s/\s\w+;/ ${OS_CODENAME};/" \
    -re"1s/${LUTRIS_VERSION}/${LUTRIS_DEBIAN_VERSION}${PPA_VERSION}/" \
    "${CODEBASE_ROOT}/debian/changelog"

# Builds and signs the debian package files.
# PPA_GPG_KEY_ID and PPA_GPG_PASSPHRASE environment variables must be defined
# by this point.
make github-ppa

# Clean up.
sudo rm -f "${CODEBASE_ROOT}/lutris-build-deps"*
git clean -df "${CODEBASE_ROOT}"
git reset --hard
