# Developer tasks for the Lutris source tree.
#
# Run `make help` to list the common developer targets.

# Everything runs inside the project's uv-managed virtualenv (.venv), which
# `uv sync` creates and keeps in step with uv.lock.
RUN:=uv run

# Diagnostics ty already reports, so `make check` only fails on new ones.
TY_BASELINE:=ty-baseline.json

# Use a flatpak-builder from the host if there is one, else the Flathub app.
FLATPAK_BUILDER:=$(shell command -v flatpak-builder 2>/dev/null || echo flatpak run org.flatpak.Builder)
FLATPAK_MANIFEST:=packaging/flatpak/net.lutris.Lutris.yml
FLATPAK_DIR:=build-flatpak

.DEFAULT_GOAL := help

help:
	@echo "Common developer tasks:"
	@echo "  make dev            Create or refresh the virtualenv (.venv)"
	@echo "  make upgrade        Upgrade every locked dependency to its newest version"
	@echo "  make run            Run Lutris from the checkout in debug mode"
	@echo "  make test           Run the unit test suite"
	@echo "  make smoke          Run the end-to-end release smoke test"
	@echo "  make cover          Run the test suite with a coverage report"
	@echo "  make check          Run every static-analysis check"
	@echo "  make style          Check code formatting (ruff format --check)"
	@echo "  make format         Auto-format code and sort imports"
	@echo "  make ty             Type check with ty against the baseline"
	@echo "  make flatpak        Build the Flatpak and install it for the current user"
	@echo "  make flatpak-bundle Build the Flatpak into a single-file lutris.flatpak"
	@echo "  make install-hooks  Install the git pre-commit hook"

# ======
# Tests
# ======

test:
	rm tests/fixtures/pga.db -f
	$(RUN) pytest

cover:
	rm tests/fixtures/pga.db -f
	rm tests/coverage/ -rf
	$(RUN) pytest --cov=lutris --cov-report=html:tests/coverage

# End-to-end checks against a throwaway profile: a fresh install and an
# upgrade of an existing one. Needs a display for the game launch checks
# (use `xvfb-run -a` when there is none).
smoke:
	utils/release-smoke-test.sh

# ==================
# Environment setup
# ==================

install-hooks:
	ln -sf -t .git/hooks/ ../../.hooks/pre-commit

dev: install-hooks
	uv sync

# Re-resolve every dependency to its newest allowed version and rewrite uv.lock.
upgrade:
	uv lock --upgrade
	uv sync

run:
	$(RUN) bin/lutris -d

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

check: ruff_lint ty syntax-compat annotation-compat po-check

ruff_lint:
	$(RUN) ruff check .

syntax-compat:
	$(RUN) python -m compileall -q lutris/

annotation-compat:
	$(RUN) python utils/check_annotations.py

po-check:
	@for f in po/*.po; do msgfmt --check "$$f" -o /dev/null; done

ty:
	$(RUN) ty check --baseline $(TY_BASELINE)

ty-update-baseline:  # Accept every current diagnostic into the baseline. Use sparingly.
	$(RUN) ty check --baseline $(TY_BASELINE) --update-baseline

# =========
# Flatpak
# =========

flatpak:
	$(FLATPAK_BUILDER) --user --install --install-deps-from=flathub --force-clean \
		--state-dir=$(FLATPAK_DIR)/state $(FLATPAK_DIR)/build $(FLATPAK_MANIFEST)

flatpak-bundle:
	$(FLATPAK_BUILDER) --install-deps-from=flathub --force-clean \
		--state-dir=$(FLATPAK_DIR)/state --repo=$(FLATPAK_DIR)/repo $(FLATPAK_DIR)/build $(FLATPAK_MANIFEST)
	flatpak build-bundle $(FLATPAK_DIR)/repo lutris.flatpak net.lutris.Lutris \
		--runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo

# =============
# Abbreviations
# =============

sc: style check
styles: style
checks: check
