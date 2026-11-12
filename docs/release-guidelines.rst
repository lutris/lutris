Release Guidelines
==================

Release and packaging automation lives in ``packaging/Makefile``. Run those
targets from the repository root, e.g. ``make -f packaging/Makefile build-source``.

Preparation
-----------
- Write changelog
- Run ``utils/release-smoke-test.sh``. It has to pass before tagging: one command,
  a few minutes, covering startup, the migrations and launching a game. Run it from
  a desktop session, or with ``xvfb-run -a``: without a display the launch and window
  checks are skipped, and the summary says so.
- Recommended, when there is time: part A of ``docs/manual-gui-checklist.rst``
  (about 10 minutes, sandbox, a genuine first start).
- Only when the release touches installers, services or the library views: part B
  of the same checklist (about 15 minutes, your own profile after a backup).
- Create git tag: ``git tag vX.Y.Z``

GitHub Release
--------------
- Draft new release: https://github.com/lutris/lutris/releases/new
- Copy changelog to release notes

Launchpad PPA
-------------
- Check the Github action has uploaded the debs to the PPA

Website
-------
- Bump version in lutris website
- Deploy website to production

OpenSUSE Build Service
----------------------
Upload to OBS (https://build.opensuse.org/package/show/home:strycore/lutris):

- ``packaging/lutris.spec``
- ``build/lutris*.dsc``
- ``build/lutris*.tar.xz``
