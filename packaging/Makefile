# Release and packaging automation for Lutris.
#
# Run these targets from the *repository root* so that debuild,
# git-buildpackage and dch operate on ./debian and ./build:
#
#     make -f packaging/Makefile <target>
#
# The github-ppa target is also invoked from CI; see
# .github/scripts/build-ubuntu-generic.sh. The AppImage workflow
# (.github/workflows/publish-appimage.yml) uses the root `make appimage`.

VERSION=`grep "__version__" lutris/__init__.py | cut -d" " -f 3 | sed 's|"\(.*\)"|\1|'`
GITBRANCH ?= master
# Default GPG key ID to use for package signing.
PPA_GPG_KEY_ID ?= 82D96E430A1F1C0F0502747E37B90EDD4E3EFAE4

.DEFAULT_GOAL := help

help:
	@echo "Release/packaging tasks (run from the repository root):"
	@echo "  make -f packaging/Makefile all|unsigned      Build .deb binaries with debuild"
	@echo "  make -f packaging/Makefile github-ppa        Build a signed source package for the PPA (CI)"
	@echo "  make -f packaging/Makefile build             Build with git-buildpackage"
	@echo "  make -f packaging/Makefile build-source      Build the source package"
	@echo "  make -f packaging/Makefile release           Build source + upload to host and PPA"
	@echo "  make -f packaging/Makefile upload            Upload the source tarball"
	@echo "  make -f packaging/Makefile upload-ppa        Upload the source package to the release PPA"
	@echo "  make -f packaging/Makefile upload-staging    Upload the source package to the staging PPA"
	@echo "  make -f packaging/Makefile snap              Build the snap"
	@echo "  make -f packaging/Makefile build-deps-ubuntu Install Debian build dependencies"
	@echo "  make -f packaging/Makefile changelog-add     Add a changelog entry (dch -i)"
	@echo "  make -f packaging/Makefile changelog-edit    Edit the changelog (dch -e)"
	@echo "  make -f packaging/Makefile clean             Remove debuild artifacts"

all:
	export GITBRANCH=master
	debuild
	debclean


unsigned:
	export GITBRANCH=master
	debuild -i -us -uc -b
	debclean


# Build process for GitHub runners.
# Requires two environment variables related to package signing.
# 	PPA_GPG_KEY_ID
#		Key ID used to sign the .deb package files.
#	PPA_GPG_PASSPHRASE
#		Decrypts the private key associated with GPG_KEY_ID.
#
# When running from a GitHub workflow.  The above environment variables
# are passed in from .github/scripts/build-ubuntu.sh and that script
# receives those variables from the .github/workflows/publish-lutris-ppa.yml
# which receives them from the repository secrets.
github-ppa:
	export GITBRANCH=master
	# Automating builds for different Ubuntu codenames manipulates the
	# version string, and so that lintian check is suppressed.  Also note
	# that all parameters after "--lintian-opts" are passed to lintian
	# so that _must_ be the last parameter.
	echo "y" | debuild -S \
		-k"${PPA_GPG_KEY_ID}" \
		-p"gpg --batch --passphrase ${PPA_GPG_PASSPHRASE} --pinentry-mode loopback" \
		--lintian-opts --suppress-tags malformed-debian-changelog-version

build-deps-ubuntu:
	sudo apt install devscripts debhelper dh-python meson

build:
	gbp buildpackage --git-debian-branch=${GITBRANCH}

clean:
	debclean

build-source: clean
	gbp buildpackage -S --git-debian-branch=${GITBRANCH}
	mkdir build
	mv ../lutris_${VERSION}* build

release: build-source upload upload-ppa


pgp-renew:
	osc signkey --extend home:strycore
	osc rebuildpac home:strycore --all

changelog-add:
	EDITOR=vim dch -i

changelog-edit:
	EDITOR=vim dch -e

upload:
	scp build/lutris_${VERSION}.tar.xz anaheim:~/volumes/releases/

upload-ppa:
	dput ppa:lutris-team/lutris build/lutris_${VERSION}*_source.changes

upload-staging:
	dput --force ppa:lutris-team/lutris-staging build/lutris_${VERSION}*_source.changes

snap:
	snapcraft clean lutris -s pull
	snapcraft