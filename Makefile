test:
	rm tests/fixtures/pga.db -f
	rm tests/coverage/ -rf
	nosetests --with-coverage --cover-package=lutris --cover-html --cover-html-dir=tests/coverage

deb-source:
	debuild -S

deb:
	debuild

changelog-add:
	dch -i

changelog-edit:
	dch -e

upload-ppa:
	dput ppa:strycore/ppa ../lutris_0.3.0_i386.changes

rpm:
	sudo alien lutris_0.3.0_all.deb --scripts --to-rpm
