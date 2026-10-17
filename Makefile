# Developer tasks for the Lutris source tree.
#
# Release, packaging and upload automation lives in packaging/Makefile and is
# run from the repository root (so debuild/git-buildpackage find ./debian) as:
#
#     make -f packaging/Makefile <target>
#
# Run `make help` to list the common developer targets.

RUN:=uv run

.DEFAULT_GOAL := help

help:
	@echo "Common developer tasks:"
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
	@echo "Release/packaging tasks: make -f packaging/Makefile help"

# ======
# Tests
# ======

test:
	rm tests/fixtures/pga.db -f
	$(RUN) nose2

cover:
	rm tests/fixtures/pga.db -f
	rm tests/coverage/ -rf
	$(RUN) nose2 --with-coverage --cover-package=lutris --cover-html --cover-html-dir=tests/coverage

# ==================
# Environment setup
# ==================

install-hooks:
	ln -sf -t .git/hooks/ ../../.hooks/pre-commit

dev: install-hooks
	uv sync --locked

# ============
# Style checks
# ============

style:
	$(RUN) ruff format . --check

format:
	$(RUN) ruff check --select I --fix
	$(RUN) ruff format .

# ===============
# Static analysis
# ===============

check: ruff_lint mypy syntax-compat annotation-compat po-check

ruff_lint:
	$(RUN) ruff check .

syntax-compat:
	$(RUN) python -m compileall -q lutris/

annotation-compat:
	$(RUN) python utils/check_annotations.py

po-check:
	@for f in po/*.po; do msgfmt --check "$$f" -o /dev/null; done

mypy:
	$(RUN) mypy . --python-version 3.10 --install-types --non-interactive 2>&1 | $(RUN) mypy-baseline filter

mypy-reset-baseline:  # Add new typing errors to mypy. Use sparingly.
	$(RUN) mypy . --python-version 3.10 --install-types --non-interactive 2>&1 | $(RUN) mypy-baseline sync

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
