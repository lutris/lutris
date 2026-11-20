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
- Bump the version with ``uv version --bump patch`` (or ``minor``, ``beta``, ...;
  see "Versioning and releases" in ``CONTRIBUTING.md``) and commit
  ``pyproject.toml`` and ``uv.lock``
- Add a ``<release>`` entry to ``share/metainfo/net.lutris.Lutris.metainfo.xml``

GitHub Release
--------------
- Push, then run the **Build Draft Release** workflow from the Actions tab. It
  builds the Flatpak and drafts a ``vX.Y.Z`` release (tag included) with
  ``Lutris-vX.Y.Z-x86_64.flatpak`` attached
- Edit the draft's notes (copy in the changelog) and publish it

Website
-------
- Bump version in lutris website
- Deploy website to production
