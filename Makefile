VERSION=`grep "__version__" lutris/__init__.py | cut -d" " -f 3 | sed 's|"\(.*\)"|\1|'`
GITBRANCH ?= master
# Default GPG key ID to use for package signing.
PPA_GPG_KEY_ID ?= 82D96E430A1F1C0F0502747E37B90EDD4E3EFAE4
PYTHON:=$(shell which python3)
PIP:=$(PYTHON) -m pip

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

test:
	rm tests/fixtures/pga.db -f
	nose2


cover:
	rm tests/fixtures/pga.db -f
	rm tests/coverage/ -rf
	nose2 --with-coverage --cover-package=lutris --cover-html --cover-html-dir=tests/coverage


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

req-python:
	pip3 install PyYAML lxml requests Pillow setproctitle python-magic distro dbus-python types-requests \
	 types-PyYAML evdev PyGObject pypresence protobuf moddb

dev:
	pip3 install ruff==0.12.1 mypy==1.16.1 mypy-baseline nose2
	pip3 install pygobject-stubs --no-cache-dir --config-settings=config=Gtk3,Gdk3,Soup2

# ============
# Style checks
# ============

style:
	ruff format . --check

format:
	ruff check --select I --fix
	ruff format .

# ===============
# Static analysis
# ===============

check: ruff_lint mypy

ruff_lint:
	ruff check .

mypy:
	mypy . --install-types --non-interactive 2>&1 | mypy-baseline filter

mypy-reset-baseline:  # Add new typing errors to mypy. Use sparingly.
	mypy . --install-types --non-interactive 2>&1 | mypy-baseline sync

# =============
# Abbreviations
# =============

sc: style check
styles: style
checks: check
