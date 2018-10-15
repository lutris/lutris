*************************************************************
/!\ This document is an early draft. It might be full of lies
*************************************************************

Contributing to Lutris (draft)
==============================

Finding issues to work on
-------------------------

If you are looking for issues to work on, have a look at the
[milestones](https://github.com/lutris/lutris/milestones) and see which one is
the closest to release then look at the tickets targeted at this release.

If you are less experienced with code, you can also have a look at the issues
that are [not part of a release](https://github.com/lutris/lutris/milestone/29)
which usually include problems with specific games or runners.

Formatting your code
--------------------

To ensure getting your contributions getting merged faster and to avoid other
developers from going back and fixing your code, please make your code pass the
pylint checks. We highly recommend that you install a pylint plugin for your
code editor. Once you have pylint set up to check the code, you can configure
it to use 120 characters max per line instead of 80.

Writing tests
-------------

If your patch does not require interactions with a GUI or external processes,
please consider adding unit tests for your code. Have a look at the existing
test suite in the `tests` folder to see what kind of features are tested.

Submitting your changes
-----------------------

Make a new git branch based of `master` in most cases, or `next` if you want to
target a future release. Send a pull request through Github describing what
issue the patch solves. If the PR is related to and existing bug report, you
can add `(Closes #nnn)` or `(Fixes #nnn)` to your PR title or message, where
`nnn` is the ticket number you're fixing. If you have been fixing your PR with
several commits, please consider squashing those commits into one with `git
rebase -i`.
