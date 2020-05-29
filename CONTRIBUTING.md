Contributing to Lutris
======================

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
issues](https://github.com/lutris/lutris/issues?q=is%3Aissue+is%3Aopen+label%3A%22need+help%22)
that can't be reproduced on the developers setup. Other issues, tagged [need
help](https://github.com/lutris/lutris/issues?q=is%3Aissue+is%3Aopen+label%3A%22need+help%22)
might be a bit more technical to resolve but you can always have a look and see
if they fit your area of expertise. Also, while not fully ready, we do
appreciate receiving translations for other languages, support for i18n will
come in a future update.

Note that Lutris is not a playground or a toy project. One cannot submit new
features that aren't on the roadmap and submit a pull request for them without
agreeing on a design first with the development team. You can submit such pull
requests but they will have to be updated with necessary changes from code
reviews of the development team. This is not only about writing good code but
also about providing good design for the overall product. Make sure to post all
the relevant information in a ticket or on the pull request. New features must
at all times have a valid use case based on an actual game, be very specific
about why you are implementing a feature otherwise it will get rejected.
Avoid adding options in the GUI or introducing new installer directives for
things that can be automated. Lutris focuses heavily on automation and on doing
the right thing by default. Only introduce new option when absolutely
necessary.

Contributors are welcome to suggest architectural changes or better code design
if they feel like the current implementation should be improved but please take
note that we're trying to stay as lean as possible. Requests introducing complex
architectural changes for the sake of "modularity", "Unix pureness" or subjective
aspects might not be received warmly. There are no plans for any rewrite in
another language or switching to another toolkit.

Running Lutris from Git
-----------------------

Running Lutris from a local git repository is easy, it only requires cloning
the repository and executing Lutris from there.

    git clone https://github.com/lutris/lutris
    cd lutris
    ./bin/lutris -d

Make sure you have all necessary dependencies installed. It is recommended that
you keep a copy of the stable version installed with your package manager to
ensure that all dependencies are available.
If you are working on newly written code that might introduce
new dependencies, check in the package configuration files for new packages to
install. Debian based distros will have their dependencies listed
in `debian/control` and RPM based ones in `lutris.spec`.

The PyGOject introspection libraries are not regular python packages and
it is not possible for pip to install them or use them from a virtualenv. Make
sure to always use PyGOject from your distribution's package manager. Also
install the necessary GObject bindings as described in the INSTALL file.

Set up your development environment
-----------------------------------

To ensure you have the proper dependencies installed run: `make dev`
This will use pipenv to create a virtual environment installing all necessary
python packages to get you up and running.

This project includes .editorconfig so you're good to go if you're using any
editor/IDE that supports this. Otherwise make sure to configure your max line
length to 120, indent style to space and always end files with an empty new line.

Formatting your code
--------------------

To ensure getting your contributions getting merged faster and to avoid other
developers from going back and fixing your code, please make sure your code
passes style checks by running `make sc` and fixing any reported issues
before submitting your code. This runs a series of tools to apply pep8 coding
style conventions, sorting and grouping imports and checking for formatting issues
and other code smells.

You can help fix formatting issues or other code smells by having a look at
the CodeFactor page: https://www.codefactor.io/repository/github/lutris/lutris

When writing docstrings, you should follow the Google style
(See: https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html)
You should always provide docstrings, otherwise your code wouldn't pass a
Pylint check.

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

QAing your changes
------------------

It is very important that any of your changes be tested manually, especially if
you didn't add unit tests for the patch. Even trivial changes should be tested
as they could potentially introduce breaking changes from a simple oversight.

Submitting your changes
-----------------------

Make a new git branch based of `master` in most cases, or `next` if you want to
target a future release. Send a pull request through GitHub describing what
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
