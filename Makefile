VERSION=`grep "__version__" lutris/__init__.py | cut -d" " -f 3 | sed 's|"\(.*\)"|\1|'`

cover:
	rm tests/fixtures/pga.db -f
	rm tests/coverage/ -rf
	nosetests --with-coverage --cover-package=lutris --cover-html --cover-html-dir=tests/coverage

test:
	rm tests/fixtures/pga.db -f
	nosetests
	flake8 lutris

deb-source: clean
	gbp buildpackage -S --git-debian-branch=${GITBRANCH}
	mkdir -p build
	mv ../lutris_0* build

deb: clean
	gbp buildpackage --git-debian-branch=${GITBRANCH}
	mkdir -p build
	mv ../lutris_0* build

changelog-add:
	EDITOR=vim dch -i

changelog-edit:
	EDITOR=vim dch -e

clean:
	rm -rf build
	debclean

build-all: deb

upload:
	scp build/lutris_${VERSION}.tar.xz lutris.net:/srv/releases/

pgp-renew:
	osc signkey --extend home:strycore
	osc rebuildpac home:strycore --all

winetricks:
	wget https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks -O share/lutris/bin/winetricks
