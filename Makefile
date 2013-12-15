test:
	rm tests/fixtures/pga.db -f
	rm tests/coverage/ -rf
	nosetests --with-coverage --cover-package=lutris --cover-html --cover-html-dir=tests/coverage

deb-source:
	debuild -S

deb:
	debuild
	mv ../lutris_0* build

changelog-add:
	dch -i

changelog-edit:
	dch -e

upload-ppa:
	dput ppa:strycore/ppa ../lutris_0.3.2_i386.changes

rpm:
	cd build && sudo alien lutris_0.3.2_all.deb --scripts --to-rpm

clean:
	debclean

build-all: deb rpm

upload:
	scp build/lutris_0.3.2_all.deb strycore.com:/srv/releases/lutris/
	scp build/lutris_0.3.2.tar.gz strycore.com:/srv/releases/lutris/
	scp build/lutris-0.3.2-2.noarch.rpm strycore.com:/srv/releases/lutris/
