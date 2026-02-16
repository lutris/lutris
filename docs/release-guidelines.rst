Release Guidelines
==================

Preparation
-----------
- Write changelog
- Create git tag: ``git tag vX.Y.Z``

GitHub Release
--------------
- Draft new release: https://github.com/lutris/lutris/releases/new
- Copy changelog to release notes
- Close the milestone

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

- ``lutris.spec``
- ``build/lutris*.dsc``
- ``build/lutris*.tar.xz``