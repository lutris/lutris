VERSION=`grep "VERSION" lutris/settings.py | cut -d" " -f 3 | sed 's|"\(.*\)"|\1|'`

cover:
	rm tests/fixtures/pga.db -f
	rm tests/coverage/ -rf
	nosetests --with-coverage --cover-package=lutris --cover-html --cover-html-dir=tests/coverage

test:
	rm tests/fixtures/pga.db -f
	nosetests3

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

clean:
	rm -rf build
	debclean

build-all: deb

upload:
	scp build/lutris_${VERSION}.tar.xz lutris.net:/srv/releases/

pgp-renew:
	osc signkey --extend home:strycore
	osc rebuildpac home:strycore --all
