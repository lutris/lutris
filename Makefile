VERSION=`grep "__version__" lutris/__init__.py | cut -d" " -f 3 | sed 's|"\(.*\)"|\1|'`
GITBRANCH ?= master
PIPENV:=pipenv
PYTHON:=$(shell which python3)
PIP:=$(PYTHON) -m pip
PIPENV_LOCK_ARGS:= --deploy --ignore-pipfile

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
	nosetests3
	flake8 lutris

cover:
	rm tests/fixtures/pga.db -f
	rm tests/coverage/ -rf
	nosetests3 --with-coverage --cover-package=lutris --cover-html --cover-html-dir=tests/coverage

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

dev:
	$(PIP) install --user --upgrade pipenv
	$(PIPENV) install --dev $(PIPENV_LOCK_ARGS) --python $(PYTHON)

requirements:
	# Generate new requirements.txt and requirements-dev.txt based on Pipfile.lock
	# These files are needed by Travis CI
	$(PIPENV) run pipenv_to_requirements -f

# ============
# Style checks
# ============

style: isort autopep8 yapf  ## Format code

isort:
	$(PIPENV) run isort -y -rc lutris

autopep8:
	$(PIPENV) run autopep8 --in-place --recursive --ignore E402 setup.py lutris

yapf:
	$(PIPENV) run yapf --style .yapf --recursive -i lutris

# ===============
# Static analysis
# ===============

check: isort-check yapf-check flake8 pylint

isort-check:
	$(PIPENV) run isort -c -rc lutris

yapf-check:
	$(PIPENV) run yapf --style .yapf --recursive --diff lutris

flake8:
	$(PIPENV) run flake8 lutris

pylint:
	$(PIPENV) run pylint --rcfile=.pylintrc --output-format=colorized lutris

# =============
# Abbreviations
# =============

sc: style check
req: requirements
styles: style
checks: check
