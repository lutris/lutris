VERSION="0.3.7"

cover:
	rm tests/fixtures/pga.db -f
	rm tests/coverage/ -rf
	nosetests --with-coverage --cover-package=lutris --cover-html --cover-html-dir=tests/coverage

test:
	rm tests/fixtures/pga.db -f
	nosetests

deb-source:
	debuild -S

deb:
	gbp buildpackage
	mv ../lutris_0* build

changelog-add:
	dch -i

changelog-edit:
	dch -e

upload-ppa:
	dput ppa:strycore/ppa ../lutris_${VERSION}_i386.changes

clean:
	rm -rf build
	debclean

build-all: deb

upload:
	scp build/lutris_${VERSION}_all.deb lutris.net:/srv/releases/
	scp build/lutris_${VERSION}.tar.gz lutris.net:/srv/releases/
