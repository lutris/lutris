# Developer tasks for the Lutris source tree.
#
# Release, packaging and upload automation lives in packaging/Makefile and is
# run from the repository root (so debuild/git-buildpackage find ./debian) as:
#
#     make -f packaging/Makefile <target>
#
# Run `make help` to list the common developer targets.

PYTHON:=$(shell which python3)

# Adding `venv` (or `v`) to any task runs it with the virtualenv in VENV_DIR instead of the system Python,
# e.g. `make run venv`, `make check venv`. `make setup venv` creates the virtualenv and installs what is missing.
VENV_DIR ?= .venv
VENV_MODE:=$(filter v venv,$(MAKECMDGOALS))
DOCTOR_ARGS:=$(if $(VENV_MODE),--venv $(VENV_DIR))
ifeq ($(VENV_MODE),)
RUN_PYTHON:=$(PYTHON)
BIN:=
PIP:=pip3
RUN_ENV:=
VENV_REQUIRED:=
else
RUN_PYTHON:=$(VENV_DIR)/bin/python
BIN:=$(VENV_DIR)/bin/
PIP:=$(RUN_PYTHON) -m pip
# bin/lutris drops sys.path entries under /home, which would hide a virtualenv kept there
RUN_ENV:=LUTRIS_ALLOW_LOCAL_PYTHON_PACKAGES=1
VENV_REQUIRED:=require-venv
endif

.DEFAULT_GOAL := help

help:
	@echo "Common developer tasks:"
	@echo "  make run            Run Lutris from the source tree (make run ARGS=\"-d\")"
	@echo "  make setup          Install the git hook and check the environment"
	@echo "  make doctor         Check the Python packages and GObject libraries Lutris needs"
	@echo "  make dev            Install development dependencies"
	@echo "  make test           Run the unit test suite"
	@echo "  make cover          Run the test suite with a coverage report"
	@echo "  make check          Run every static-analysis check"
	@echo "  make style          Check code formatting (ruff format --check)"
	@echo "  make format         Auto-format code and sort imports"
	@echo "  make mypy           Run mypy against the baseline"
	@echo "  make appimage       Build the AppImage"
	@echo "  make install-hooks  Install the git pre-commit hook"
	@echo
	@echo "Add venv (or v) to a task to use the virtualenv in .venv instead of the system Python,"
	@echo "e.g. make run venv, make check venv (VENV_DIR=path to change it)."
	@echo "make setup venv creates the virtualenv if needed and installs what is missing."
	@echo
	@echo "Release/packaging tasks: make -f packaging/Makefile help"

require-venv:
	@test -x $(VENV_DIR)/bin/python || { echo "No virtualenv at $(VENV_DIR); create it with: make setup venv"; exit 1; }

# =====
# Run
# =====

run: $(VENV_REQUIRED)
	$(RUN_ENV) $(RUN_PYTHON) bin/lutris $(ARGS)

# ======
# Tests
# ======

test: $(VENV_REQUIRED)
	rm tests/fixtures/pga.db -f
	$(BIN)nose2

cover: $(VENV_REQUIRED)
	rm tests/fixtures/pga.db -f
	rm tests/coverage/ -rf
	$(BIN)nose2 --with-coverage --cover-package=lutris --cover-html --cover-html-dir=tests/coverage

# ==================
# Environment setup
# ==================

req-python: $(VENV_REQUIRED)
	$(PIP) install PyYAML lxml requests Pillow setproctitle python-magic distro dbus-python evdev \
	 PyGObject pypresence protobuf moddb

doctor:
	$(PYTHON) utils/doctor.py $(DOCTOR_ARGS)

# `make setup venv` also creates VENV_DIR if needed and installs the missing packages and dev tools into it
setup:
	$(PYTHON) utils/doctor.py --setup $(DOCTOR_ARGS)

v venv:
	@test -n "$(filter-out v venv,$(MAKECMDGOALS))" || echo "'make $@' is a modifier for another task, e.g. make run $@ or make check $@"

install-hooks:
	ln -sf -t .git/hooks/ ../../.hooks/pre-commit

dev: $(VENV_REQUIRED) install-hooks
	$(PIP) install ruff==0.12.1 mypy==1.16.1 mypy-baseline nose2 types-requests types-PyYAML
	$(PIP) install 'pygobject-stubs>=2.18.0' --no-cache-dir --config-settings=config=Gtk3,Gdk3,Soup2

# ============
# Style checks
# ============

style: $(VENV_REQUIRED)
	$(BIN)ruff format . --check

format: $(VENV_REQUIRED)
	$(BIN)ruff check --select I --fix
	$(BIN)ruff format .

# ===============
# Static analysis
# ===============

check: ruff_lint mypy syntax-compat annotation-compat po-check

ruff_lint: $(VENV_REQUIRED)
	$(BIN)ruff check .

syntax-compat: $(VENV_REQUIRED)
	$(RUN_PYTHON) -m compileall -q lutris/

annotation-compat: $(VENV_REQUIRED)
	$(RUN_PYTHON) utils/check_annotations.py

po-check:
	@for f in po/*.po; do msgfmt --check "$$f" -o /dev/null; done

mypy: $(VENV_REQUIRED)
	$(BIN)mypy . --python-version 3.10 --install-types --non-interactive 2>&1 | $(BIN)mypy-baseline filter

mypy-reset-baseline: $(VENV_REQUIRED)  # Add new typing errors to mypy. Use sparingly.
	$(BIN)mypy . --python-version 3.10 --install-types --non-interactive 2>&1 | $(BIN)mypy-baseline sync

# ==============================
# Packaging (developer-facing)
# ==============================

appimage:
	utils/appimage/build.sh

# =============
# Abbreviations
# =============

sc: style check
styles: style
checks: check
