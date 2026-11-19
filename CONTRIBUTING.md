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

    git clone https://github.com/lutris/lutris
    cd lutris
    make dev    # creates .venv with `uv sync` and installs the git pre-commit hook
    make run    # same as `uv run bin/lutris -d`

uv downloads a Python interpreter if it doesn't find a suitable one
(`.python-version` names the preferred release). Any `uv run <command>` runs
in the project environment and brings it up to date first; you can also
`source .venv/bin/activate` and run `./bin/lutris -d` directly.

PyGObject, pycairo, dbus-python and evdev are built from source the first time,
so you need a C compiler, `pkg-config` and these development headers:

* Fedora: `gcc pkgconf-pkg-config gobject-introspection-devel cairo-devel cairo-gobject-devel dbus-devel kernel-headers`
* Debian/Ubuntu: `build-essential pkg-config libgirepository-2.0-dev libcairo2-dev libdbus-1-dev linux-libc-dev`
* Arch: `base-devel gobject-introspection cairo dbus linux-api-headers`

The libraries Lutris loads through GObject introspection still come from your
system: GTK 3, WebKitGTK 4.1, libnotify and gnome-desktop 3, along with the
rest of the runtime dependencies listed in `debian/control` (Debian based
distros) or `packaging/lutris.spec` (RPM based ones).

Managing dependencies
---------------------

Python dependencies are declared in `pyproject.toml` and locked in `uv.lock`,
which is committed. CI installs with `--locked` and fails if the two disagree.

* Add a runtime dependency with `uv add <package>`, a development tool with
  `uv add --group lint|typing|test <package>`.
* `make upgrade` (`uv lock --upgrade`) moves every package to its newest
  allowed version; `uv lock --upgrade-package <package>` moves just one.
* Commit `pyproject.toml` and `uv.lock` together.

Development tools are split into dependency groups so CI jobs install only
what they run: `lint` (ruff), `typing` (mypy and stubs) and `test` (nose2).
`dev` includes all three and is what `uv sync` installs by default.

This project includes .editorconfig so you're good to go if you're using any
editor/IDE that supports this. Otherwise make sure to configure your max line
length to 120, indent style to space and always end files with an empty new line.

### NixOS

On NixOS (or anywhere with Nix), the `shell.nix` at the root of the repository
provides the interpreter, the C libraries and headers, every GObject typelib and
the external tools Lutris needs:

    nix-shell
    ./bin/lutris -d

Entering the shell runs `uv sync` against the Nix Python and activates `.venv`,
so the Python packages come from `uv.lock` exactly as on any other system.

The shell is enough to work on the client and run the test suite, but the
runners Lutris downloads (Wine, Proton, ...) are generic Linux binaries that
won't run on NixOS as-is. To launch games from your checkout, install
`steam-run` (it's unfree; `programs.steam.enable = true;` also provides it)
and start Lutris from the repository root with the helper the shell provides:

    lutris-steam-run -d

Plain `steam-run ./bin/lutris` doesn't work: inside it, `python3` resolves to
steam-run's own interpreter (no PyGObject), and `GIO_EXTRA_MODULES` is dropped,
which disables TLS in Lutris and its web views.

When adding a system library or tool, add it to `shell.nix` as well.

Formatting your code
--------------------

To ensure getting your contributions getting merged faster and to avoid other
developers from going back and fixing your code, please make sure your code
passes style checks by running `make sc` and fixing any reported issues
(`make format` fixes formatting and import order for you)
before submitting your code. This runs a series of tools to apply PEP 8 coding
style conventions, sorting and grouping imports and checking for formatting issues
and other code smells.

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
You can run the test suite by typing `make test` in the source directory.

QAing your changes
------------------

It is very important that any of your changes be tested manually, especially if
you didn't add unit tests. Even trivial changes should be tested
as they could potentially introduce breaking changes from a simple oversight.

Submitting your changes
-----------------------

Make a new git branch based of `master` in most cases. Send a pull request
through GitHub describing what issue the patch solves.
If the PR is related to and existing bug report, you can add `(Closes #nnnn)`
or `(Fixes #nnnn)` to your PR title or message, where `nnnn` is the ticket
number you're fixing.

If you contribute to Lutris on a somewhat regular basis, be sure to add
yourself to the AUTHORS file!


Developer resources
-------------------

Lutris uses Python 3 and GObject / Gtk+ 3 as its core stack, here are some
links to some resources that can help you familiarize yourself with the
project's code base.

* [Python 3 documentation](https://docs.python.org/3/)
* [PyGObject documentation](https://pygobject.readthedocs.io/en/latest/)
* [Python Gtk 3 tutorial](https://python-gtk-3-tutorial.readthedocs.io/en/latest/objects.html)

Project structure
-----------------

    [root]-+ Config files and READMEs (pyproject.toml, meson.build, Makefile)
        |
        +-[bin] Main lutris executable script
        +-[debian] Debian / Ubuntu packaging configuration
        +-[docs] User documentation
        +-[lutris]-+ Source folder
        |          |
        |          +-[gui] Gtk UI code
        |          +-[installer] Install script interpreter
        |          +-[migrations] Migration scripts for user side changes
        |          +-[runners] Runner code, detailing launch options and settings
        |          +-[services] External services (Steam, GOG, ...)
        |          +-[util] Generic utilities
        |
        +-[packaging] RPM spec and release/packaging Makefile
        +-[po] Translation files
        +-[share] Lutris resources like icons, ui files, scripts
        +-[tests] Unit tests
        +-[utils] Helper scripts and the AppImage build

Build tooling
-------------

* ``pyproject.toml`` is the single source of truth for Python packaging
  metadata and for ruff/mypy/pyright configuration.
* ``meson.build`` (plus ``po/meson.build``) drives the install layout used by
  distro packages.
* The root ``Makefile`` holds developer tasks only. Release, packaging and
  upload targets live in ``packaging/Makefile``.
