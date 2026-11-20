Contributing to Lutris
======================

Note regarding AI and human contributions
-----------------------------------------

All contributions regardless of how they were generated are subject to the same level of scrutiny and are expected to be useful, understandable and validated.
You are free to use any tool available to help you create your contributions.
Contributions that break those rules are subject to being closed without notice.
If we are particularly impressed by how bad a contribution, we reserve the right to instantly and permanently ban the author from our Github account without notice.


Finding features to work on
---------------------------

If you are looking for issues to work on, have a look at the
[milestones](https://github.com/lutris/lutris/milestones) and see which one is
the closest to release then look at the tickets targeted at this release.

Don't forget that Lutris is not only a desktop client, there are also a lot of
issues to work on [on the website](https://github.com/lutris/website/issues)
and also in the [build scripts repository](https://github.com/lutris/buildbot)
where you can submit bash scripts for various open source games and engines we
do not already have.

Another area where users can help is [confirming some
issues](https://github.com/lutris/lutris/issues?q=is%3Aissue+is%3Aopen+label%3A%22can%27t+reproduce%22+)
that can't be reproduced on the developers setup. Please make sure that you're able to
reproduce an issue before attempting to fix it.

Note that Lutris is not a playground or a toy project. One cannot submit new
features that aren't on the roadmap and submit a pull request for them without
agreeing on a design first with the development team. Please get in touch with
the developers before writing any code, so that you don't waste your efforts on
something that isn't going to be merged. Make sure to post all
the relevant information in a ticket or on the pull request. New features must
at all times have a valid use case based on an actual game, be very specific
about why you are implementing a feature otherwise it will get rejected.
Avoid adding options in the GUI or introducing new installer directives for
things that can be automated. Lutris focuses heavily on automation and on doing
the right thing by default. Only introduce new options when absolutely
necessary.

Contributors are welcome to suggest architectural changes or better code design
if they feel like the current implementation should be improved but please take
note that we're trying to stay as lean as possible. Requests introducing complex
architectural changes for the sake of "modularity", "Unix pureness" or subjective
aspects might not be received warmly. There are no current plans for any rewrite in
another language. Once again, make sure to discuss any change with a core developer
before writing a large amount of code. Keeping your pull requests as small as a possible
is the best way to have them reviewed and merged quickly.

Running Lutris from Git
-----------------------

Lutris is developed in a virtualenv managed by [uv](https://docs.astral.sh/uv/),
which installs every Python dependency, PyGObject included, at the versions
pinned in `uv.lock`. Install uv, then:

    git clone https://github.com/jedace07/lutris
    cd lutris
    uv run lutris -d

uv downloads and uses its own build of Python 3.14 (`.python-version`), never
the system's. Lutris is locked to 3.14 because that's what the Flatpak's GNOME
runtime ships, so you develop on what users run. Any `uv run <command>` runs
in the project environment and brings it up to date first; you can also
`source .venv/bin/activate` and run `lutris -d` directly. To enable the
optional pre-commit hook, run `git config core.hooksPath .hooks`.

PyGObject, pycairo, dbus-python and evdev are built from source the first
time. PySide6 Essentials includes Qt Quick. `INSTALL.rst` lists the system
packages for Fedora, Debian/Ubuntu and Arch.

`uv run lutris -d` launches Qt Quick using your normal Lutris profile.
Run the Qt tests with `uv run pytest tests/qt`; they use the offscreen platform.

See `INSTALL.rst` to build and install the Flatpak from your working tree.

Managing dependencies
---------------------

Python dependencies are declared in `pyproject.toml` and locked in `uv.lock`,
which is committed. CI installs with `--locked` and fails if the two disagree.

* Add a runtime dependency with `uv add <package>`, a development tool with
  `uv add --group lint|typing|test <package>`.
* `uv lock --upgrade` moves every package to its newest
  allowed version; `uv lock --upgrade-package <package>` moves just one.
* Commit `pyproject.toml` and `uv.lock` together.

Development tools are split into dependency groups so CI jobs install only
what they run: `lint` (ruff), `typing` (ty and stubs) and `test` (pytest).
`dev` includes all three and is what `uv sync` installs by default.

Versioning and releases
-----------------------

The version's one canonical place is `version` in `pyproject.toml`. Lutris
reads it from there when running from a checkout and from the package metadata
when installed. Change it with `uv version`,
which updates `pyproject.toml` and `uv.lock` together:

```bash
# Stable patch: 0.5.23 -> 0.5.24
uv version --bump patch

# First beta of the next minor: 0.5.23 -> 0.6.0b1
uv version --bump minor --bump beta

# Subsequent beta: 0.6.0b1 -> 0.6.0b2
uv version --bump beta

# Promote a prerelease: 0.6.0b2 -> 0.6.0
uv version --bump stable
```

Flatpak bundles built by CI are named after the version. Prereleases also get
the commit they were built from (`Lutris-v0.6.0b1+g1a2b3c4-x86_64.flatpak`), or
`+local` when built elsewhere, so two builds of the same beta can be told apart.

To release, bump the version, add a `<release>` entry to
`packaging/desktop/share/metainfo/net.lutris.Lutris.metainfo.xml`, push, then run the **Build
Draft Release** workflow from the Actions tab. It builds the Flatpak and drafts
a `v<version>` release (marked as a prerelease for alphas, betas and release
candidates) with the bundle attached; review the notes and publish it. See
`docs/release-guidelines.rst` for the checks to run first.

This project includes .editorconfig so you're good to go if you're using any
editor/IDE that supports this. Otherwise make sure to configure your max line
length to 120, indent style to space and always end files with an empty new line.

Formatting your code
--------------------

To ensure getting your contributions getting merged faster and to avoid other
developers from going back and fixing your code, please make sure your code
passes `uv run ruff check .`, `uv run ruff format --check .`, and
`uv run ty check --baseline ty-baseline.json`. To sort imports and fix
formatting, run `uv run ruff check --select I --fix .` and `uv run ruff format .`.

You can help fix formatting issues or other code smells by having a look at
the CodeFactor page: https://www.codefactor.io/repository/github/lutris/lutris

Writing tests
-------------

If your patch does not require interactions with a GUI or external processes,
please consider adding unit tests for your code. Have a look at the existing
test suite in the `tests` folder to see what kind of features are tested.

Running tests
-------------

Be sure to test your changes thoroughly, never submit changes without running
the code. Also run the test suite and check that nothing broke.
Run the suite with `QT_QPA_PLATFORM=offscreen uv run pytest`. Use
`uv run pytest tests/util` or `uv run pytest -k steam` to narrow it down.

QAing your changes
------------------

It is very important that any of your changes be tested manually, especially if
you didn't add unit tests. Even trivial changes should be tested
as they could potentially introduce breaking changes from a simple oversight.

Submitting your changes
-----------------------

Make a new git branch based off `main` in most cases. Send a pull request
through GitHub describing what issue the patch solves.
If the PR is related to and existing bug report, you can add `(Closes #nnnn)`
or `(Fixes #nnnn)` to your PR title or message, where `nnnn` is the ticket
number you're fixing.

If you contribute to Lutris on a somewhat regular basis, be sure to add
yourself to the AUTHORS file!


Developer resources
-------------------

Lutris uses Python 3.14, Gio/GLib and Qt Quick.

* [Python 3 documentation](https://docs.python.org/3/)
* [PyGObject documentation](https://pygobject.readthedocs.io/en/latest/)
* [Qt Quick documentation](https://doc.qt.io/qt-6/qtquick-index.html)

Project structure
-----------------

    [root]-+ Config files and READMEs (pyproject.toml, uv.lock)
        |
        +-[docs] User documentation
        +-[lutris]-+ Source folder
        |          |
        |          +-[backend] Plain-data frontend API
        |          +-[cli] Headless command-line frontend
        |          +-[data] Runtime artwork, runner definitions and game wrapper
        |          +-[locale] Gettext translations
        |          +-[qt] Qt Quick frontend (controllers and QML)
        |          +-[installer] Install script interpreter
        |          +-[migrations] Migration scripts for user side changes
        |          +-[runners] Runner code, detailing launch options and settings
        |          +-[services] External services (Steam, GOG, ...)
        |          +-[util] Generic utilities
        |
        +-[packaging] Flatpak manifest and desktop metadata
        +-[tests] Unit tests
        +-[utils] Helper scripts

Build tooling
-------------

* `pyproject.toml` declares the `lutris` console command and builds the Python
  package with `uv build`. It also configures ruff, ty, pytest and pyright.
* ``ty-baseline.json`` lists the type errors ty already reports, so CI only
  fails on new ones. Fix entries rather than adding to it.
* `packaging/flatpak` holds the Flatpak manifest, which installs the same uv-built
  wheel. `shared-modules` is a git submodule of Flathub's shared modules.

The core doesn't import frontends or GUI toolkits. Read `docs/architecture.rst`
before changing the boundary between the backend and either frontend. The
architecture and frontend API tests enforce it.
