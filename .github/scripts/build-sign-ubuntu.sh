#!/bin/bash -e
# This script is intended to be run as part of a GitHub workflow where we
# build multiple times under different OS versions, which _may_ produce
# differences in the built packages.
#
# It expects the following environment variables:
# 	PPA_GPG_PRIVATE_KEY
#		Private key with access to the Ubuntu PPA.
#	PPA_GPG_PASSPHRASE
#		Decrypts the above private key.

# This gets the Ubuntu codename & version from the local OS.
OS_CODENAME="$(grep 'VERSION_CODENAME=' /etc/os-release | cut -f2 -d'=' | tr -d '"')"
OS_VERSION="$(grep 'VERSION_ID=' /etc/os-release | cut -f2 -d'=' | tr -d '"')"

# Get the base Lutris version in the same way that the Makefile does.
LUTRIS_VERSION=$(grep "__version__" lutris/__init__.py | cut -d" " -f 3 | sed 's|"\(.*\)"|\1|')

# Creates a GPG keyring using the key passed from the GitHub workflow.
echo "::group::Importing GPG private key..."
PPA_GPG_KEY_ID=$(echo "${PPA_GPG_PRIVATE_KEY}" | gpg --import-options show-only --import | sed -n '2s/^\s*//p')
export PPA_GPG_KEY_ID
echo "${PPA_GPG_KEY_ID}"
echo "${PPA_GPG_PRIVATE_KEY}" | gpg --batch --passphrase "${PPA_GPG_PASSPHRASE}" --import
echo "::endgroup::"

# May as well since we don't need after at this point.
unset PPA_GPG_PRIVATE_KEY

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

# Does an initial make process for creating a debian source package.
echo "::group::Building deb for: $OS_VERSION ($OS_CODENAME)"
debmake -n -p lutris -u "${LUTRIS_VERSION}" -b":python3"

# Updates debian/control file based on current environment.
sudo mk-build-deps --install \
    --tool='apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends --yes' \
    debian/control

# Update the changelog entry. Specifically we change the top most
# changelog entry codename to match our current OS and the version
# number to match the Debian+PPA version scheme described above.
sed -i"" \
    -re"1s/\s\w+;/ ${OS_CODENAME};/" \
    -re"1s/${LUTRIS_VERSION}/${LUTRIS_DEBIAN_VERSION}${PPA_VERSION}/" \
    debian/changelog

# Builds and signs the debian package files.
# PPA_GPG_KEY_ID and PPA_GPG_PASSPHRASE environment variables must be defined
# by this point.
make github-ppa
echo "::endgroup::"

# Clean up build dependencies.
sudo rm -f lutris-build-deps*
