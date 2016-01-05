VERSION="0.3.7.2"

cover:
	rm tests/fixtures/pga.db -f
	rm tests/coverage/ -rf
	nosetests --with-coverage --cover-package=lutris --cover-html --cover-html-dir=tests/coverage

test:
	rm tests/fixtures/pga.db -f
	nosetests

deb-source: clean
	gbp buildpackage -S
	mkdir -p build
	mv ../lutris_0* build

deb: clean
	gbp buildpackage
	mkdir -p build
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
	scp build/lutris_${VERSION}.tar.gz lutris.net:/srv/releases/
