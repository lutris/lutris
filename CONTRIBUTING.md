Contributing to Lutris
======================

Finding issues to work on
-------------------------

If you are looking for issues to work on, have a look at the
[milestones](https://github.com/lutris/lutris/milestones) and see which one is
the closest to release then look at the tickets targeted at this release.

If you are less experienced with code, you can also have a look at the issues
that are [not part of a release](https://github.com/lutris/lutris/milestone/29)
which usually include problems with specific games or runners.

Don't forget that lutris is not only a desktop client, there are also a lot of
issues to work on [on the website](https://github.com/lutris/website/issues)
and also in the [build scripts repository](https://github.com/lutris/buildbot)
where you can submit bash scripts for various open source games and engines we
do not already have.

Other areas can benefit non technical help. The Lutris UI is far from being
perfect and could use the input of people experienced with UX and design.
Also, while not fully ready, we do appreciate receiving translations for other
languages. Support for i18n will come in a future update.

Another area where users can help is [confirming some
issues](https://github.com/lutris/lutris/issues?q=is%3Aissue+is%3Aopen+label%3A%22need+help%22)
that can't be reproduced on the developers setup. Other issues, tagged [need
help](https://github.com/lutris/lutris/issues?q=is%3Aissue+is%3Aopen+label%3A%22need+help%22)
might be a bit more technical to resolve but you can always have a look and see
if they fit your area of expertise.

Running Lutris from Git
-----------------------

Running Lutris from a local git repository is easy, it only requires cloning
the repository and executing Lutris from there.

    git clone https://github.com/lutris/lutris
    cd lutris
    ./bin/lutris -d

Make sure you have all necessary dependencies installed. It is recommended that
you keep a stable copy of the client installed with your package manager to
ensure that all dependencies are available.
If you are working on a branch implementing new features, such as the `next`
branch, it might introduce new dependencies. Check in the package configuration
files for new dependencies, for example Debian based distros will have their
dependencies listed in `debian/control` and in `lutris.spec` for RPM based
ones.

Under NO circumstances should you use a virtualenv or install dependencies with
pip. The PyGOject introspection libraries are not regular python packages and
it is not possible to pip install them or use them from a virtualenv. Make
sure to always use PyGOject from your distribution's package manager.

Formatting your code
--------------------

To ensure getting your contributions getting merged faster and to avoid other
developers from going back and fixing your code, please make your code pass the
pylint checks. We highly recommend that you install a pylint plugin for your
code editor. Once you have pylint set up to check the code, you can configure
it to use 120 characters max per line instead of 80.

You can help fixing formatting issues or other code smells by having a look at
the CodeFactor page: https://www.codefactor.io/repository/github/lutris/lutris

When writing docstrings, you should follow the Google style
(See: https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html)

Do *not* add type annotations, those are not supported in Python 3.4.

Writing tests
-------------

If your patch does not require interactions with a GUI or external processes,
please consider adding unit tests for your code. Have a look at the existing
test suite in the `tests` folder to see what kind of features are tested.

Running tests
-------------

Be sure to test your changes thoroughly, never submit changes without running
the code. At the very least, run the test suite and check that nothing broke.
You can run the test suite by typing `make test` in the source directory.
In order to run the test, you'll need to install nosetests and flake8:

    pip3 install nose flake8

Submitting your changes
-----------------------

Make a new git branch based of `master` in most cases, or `next` if you want to
target a future release. Send a pull request through Github describing what
issue the patch solves. If the PR is related to and existing bug report, you
can add `(Closes #nnn)` or `(Fixes #nnn)` to your PR title or message, where
`nnn` is the ticket number you're fixing. If you have been fixing your PR with
several commits, please consider squashing those commits into one with `git
rebase -i`.

Developer resources
-------------------

Lutris uses Python 3 and GObject / Gtk+ 3 as its core stack, here are some
links to some resources that can help you familiarize yourself with the
project's code base.

* [Python 3 documentation](https://docs.python.org/3/)
* [PyGObject documentation](https://pygobject.readthedocs.io/en/latest/)
* [Python Gtk 3 tutorial](https://python-gtk-3-tutorial.readthedocs.io/en/latest/objects.html)
* [Fakegir GObject code completion](https://github.com/strycore/fakegir)

Project structure
-----------------

    [root]-+ Config files and READMEs
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
        +-[po] Translation files
        +-[share] Lutris resources like icons, ui files, scripts
        +-[tests] Unit tests
