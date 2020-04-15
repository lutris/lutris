VERSION=`grep "__version__" lutris/__init__.py | cut -d" " -f 3 | sed 's|"\(.*\)"|\1|'`
GITBRANCH ?= master

all:
	export GITBRANCH=master
	debuild
	debclean

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
	nosetests
	flake8 lutris

cover:
	rm tests/fixtures/pga.db -f
	rm tests/coverage/ -rf
	nosetests --with-coverage --cover-package=lutris --cover-html --cover-html-dir=tests/coverage

pgp-renew:
	osc signkey --extend home:strycore
	osc rebuildpac home:strycore --all

changelog-add:
	dch -i

changelog-edit:
	dch -e

upload:
	scp build/lutris_${VERSION}.tar.xz lutris.net:/srv/releases/

upload-ppa:
	dput ppa:lutris-team/lutris build/lutris_${VERSION}*_source.changes

upload-staging:
	dput --force ppa:lutris-team/lutris-staging build/lutris_${VERSION}*_source.changes

snap:
	snapcraft clean lutris -s pull
	snapcraft
