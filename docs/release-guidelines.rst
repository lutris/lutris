Release Guidelines
==================

Release and packaging automation lives in ``packaging/Makefile``. Run those
targets from the repository root, e.g. ``make -f packaging/Makefile build-source``.

Preparation
-----------
- Write changelog
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
