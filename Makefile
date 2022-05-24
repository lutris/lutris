VERSION=`grep "__version__" lutris/__init__.py | cut -d" " -f 3 | sed 's|"\(.*\)"|\1|'`
GITBRANCH ?= master
PYTHON:=$(shell which python3)
PIP:=$(PYTHON) -m pip

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

dev:
	pip3 install isort flake8 pylint autopep8

# ============
# Style checks
# ============

style: isort autopep8  ## Format code

isort:
	isort lutris

autopep8:
	autopep8 --in-place --recursive --ignore E402 setup.py lutris


# ===============
# Static analysis
# ===============

check: isort-check flake8 pylint

isort-check:
	isort lutris -c

flake8:
	flake8 . --count --max-complexity=25 --max-line-length=120 --show-source --statistics

pylint:
	pylint lutris --rcfile=.pylintrc --output-format=colorized

bandit:
	bandit . --recursive --skip B101,B105,B107,B108,B303,B310,B311,B314,B320,B404,B405,B410,B602,B603,B607,B608

black:
	black . --check

mypy:
	mypy . --ignore-missing-imports --install-types --non-interactive

# =============
# Abbreviations
# =============

sc: style check
styles: style
checks: check
