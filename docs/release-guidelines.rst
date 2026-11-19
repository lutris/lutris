Release Guidelines
==================

Preparation
-----------
- Write changelog
- Run ``utils/release-smoke-test.sh``. It has to pass before tagging: one command,
  a few minutes, covering startup, the migrations and launching a game. It needs a
  display: run it from a desktop session or with ``xvfb-run -a``. Without one the
  client cannot start, so every check but ``--version`` fails.
- Recommended, when there is time: part A of ``docs/manual-gui-checklist.rst``
  (about 10 minutes, sandbox, a genuine first start).
- Only when the release touches installers, services or the library views: part B
  of the same checklist (about 15 minutes, your own profile after a backup).
- Bump ``version`` in ``pyproject.toml`` and ``__version__`` in ``lutris/__init__.py``
- Create git tag: ``git tag vX.Y.Z``

GitHub Release
--------------
- Draft new release: https://github.com/jedace07/lutris/releases/new
- Copy changelog to release notes
- Publishing the release runs the Flatpak workflow, which attaches
  ``Lutris-X.Y.Z-x86_64.flatpak`` to it; check that it's there

Website
-------
- Bump version in lutris website
- Deploy website to production
