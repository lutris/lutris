Manual GUI checklist
====================

The automated release smoke test (``utils/release-smoke-test.sh``) covers
everything that can be driven from the command line. This page covers the part
that still has to be clicked: the ten items the script prints when it finishes,
and how to open the client with the profiles the script prepared.

Budget about ten minutes for the two test profiles, plus the same items again on
your own profile for the full "existing install" coverage.

Prerequisites
-------------

- A desktop session (X11 or Wayland). The GUI items cannot be done headless.
- The repository checked out with its dependencies installed; see
  ``CONTRIBUTING.md``. Activate the virtualenv first, the commands below use the
  same interpreter as the script.
- A normal user account. Lutris refuses to start as root.
- **No Lutris instance running.** Lutris is a single-instance application
  (``net.lutris.Lutris`` on the session bus), so a second client only raises the
  one that is already running instead of doing what you asked. Close your own
  Lutris, including the version in the tray, before you start.
- Optional, for item 8: at least one game service (Steam, GOG, Epic, ...)
  installed and logged in on the machine.

Step 1 - Run the automated part and keep the sandbox
----------------------------------------------------

The profiles used by the GUI pass are built by the script, inside a temporary
directory that it deletes on exit. Pass ``--keep`` so it survives::

    ./utils/release-smoke-test.sh --keep

When it finishes, the script prints the sandbox path and a ``launch()`` shell
function that opens the client with each test profile. Keep that terminal
around; every profile below lives inside ``$SMOKE``.

If a check fails, treat it as a release blocker and report it before spending
time on the GUI pass. The stdout/stderr of every check is kept in the sandbox.

Step 2 - What is inside the sandbox
-----------------------------------

::

    $SMOKE/
      fresh/
        home/                          HOME of the first-run profile
          .local/share/lutris/         pga.db, lutris.conf, games/, runners/
          .cache/lutris/               lutris.log, installer/, shaders/, tmp/
        games/smoke-fresh-game/        seeded test game (fake-game.sh)
        logs/                          stdout and stderr of every check
      existing/
        home/                          HOME of the upgraded profile
        games/legacy-emulator/         seeded game with a pre-"platform" config
        games/smoke-existing-game/     seeded game added before the upgrade
      clone/                           only with --existing-profile

Things worth knowing before you start clicking:

- Settings live in ``$SMOKE/<profile>/home/.local/share/lutris/lutris.conf``.
  ``~/.config/lutris`` is the deprecated location and is not used.
- The seeded games are two-line shell scripts (``fake-game.sh``) that write a
  ``launched.marker`` file and exit immediately. That is deliberate: it makes
  the launch checks work without a download, a Wine prefix or a GPU.

The three profiles and the items that use them:

``fresh``
    A machine where Lutris never ran. Items 1, 3, 4, 5, 6, 7 and 10.

``existing``
    An upgrade: a library, old game configs and an old ``migration_version``.
    Items 2, 4, 8, 9 and 10.

``clone``
    A copy of your real profile, only created with ``--existing-profile``.
    Optional, items 2 and 9.

Step 3 - Open a test profile
----------------------------

Never launch ``bin/lutris`` bare for these checks: that opens your real profile.
Point ``HOME`` and the XDG directories at the sandbox instead. The script prints
this snippet, ready to paste (``$REPO`` is your checkout)::

    SMOKE=/tmp/lutris-smoke.XXXXXXXX
    REPO=/path/to/lutris                 # your checkout
    launch() {
        env HOME="$SMOKE/$1/home" \
            XDG_DATA_HOME="$SMOKE/$1/home/.local/share" \
            XDG_CONFIG_HOME="$SMOKE/$1/home/.config" \
            XDG_CACHE_HOME="$SMOKE/$1/home/.cache" \
            LUTRIS_ALLOW_LOCAL_PYTHON_PACKAGES=1 \
            "$REPO/.venv/bin/python" "$REPO/bin/lutris" -d
    }

    launch fresh
    # ... do the fresh-profile items, then quit the client with Ctrl+Q ...
    launch existing

Notes:

- Drop ``-d`` to see the client the way a normal user would; keep it while
  testing, it is what makes a failure diagnosable.
- ``LUTRIS_ALLOW_LOCAL_PYTHON_PACKAGES=1`` is required because ``bin/lutris``
  removes ``/home`` entries from ``sys.path`` unless it is set, which would hide
  the virtualenv.
- Quit the client before opening another profile, see the single-instance note
  above.
- The log of the running profile is
  ``$SMOKE/<profile>/home/.cache/lutris/lutris.log``.
- Start over with: ``rm -rf $SMOKE`` and re-run the script with ``--keep``; it
  prints a new path.

Step 4 - The checklist
----------------------

Each item lists what to do, what a pass looks like, and what to attach if it
fails. Work through the items for one profile, then the other.

Item 1 - First start (``fresh``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** ``launch fresh``.

**Pass:** the window opens within a few seconds. The header bar has a search
entry ("Search games"), an "Add Game" button, a view toggle and the main menu.
The sidebar shows **Library** (Games, Recent, Favorites, Uncategorized, Hidden,
Missing, Running) followed by **Categories**, **Sources**, **Runners** and
**Platforms**. The library shows the seeded "Smoke Fresh Game". No error dialog,
no "Do not run Lutris as root" notice, and nothing about a missing database.

**If it fails:** attach ``$SMOKE/fresh/home/.cache/lutris/lutris.log`` and the
console output of the launch.

Item 2 - Library rendering (``existing``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** ``launch existing``, then:

- type ``smoke`` in the "Search games" entry, then clear it;
- switch the view with the "Toggle View" button;
- click **Recent** and **Games** in the sidebar;
- right-click a game → **Categories**, add a category, save.

**Pass:** both seeded games are listed ("Smoke Existing Game" and "Legacy
Emulator Game"); the search narrows the library and clearing it restores it; the
list and grid views both render the covers (or placeholders) without crashing;
the sidebar counts match the library; the category is kept after saving.

**If it fails:** note which entry is missing or misrendered, and which action
triggered it.

Item 3 - Add a locally installed game (``fresh``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** click "Add Game" → in the "Add games to Lutris" dialog pick **Add
locally installed game** → **Continue**. Name it ``GUI Smoke Test``, set
**Runner** to ``Linux``, open the **Game options** tab and set **Executable** to
``$SMOKE/fresh/games/smoke-fresh-game/fake-game.sh``, then **Save**.

**Pass:** the game dialog closes, the new game appears in the library, and it is
still there after quitting and running ``launch fresh`` again.

**On disk:** a new ``$SMOKE/fresh/home/.local/share/lutris/games/<slug>-<ts>.yml``
and a row in ``pga.db``. Deleting the game from the context menu (**Remove**)
removes both.

Item 4 - Play from the GUI, then stop (both profiles)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** the seeded games exit immediately, so for this item point the game at
something that stays alive, then play it from the GUI::

    printf '#!/bin/sh\nsleep 30\n' > "$SMOKE/fresh/games/sleepy.sh"
    chmod +x "$SMOKE/fresh/games/sleepy.sh"

Then right-click the game → **Configure** → **Game options** → **Executable** →
``sleepy.sh`` → **Save**. Double-click the game to play it.

**Pass:** the game starts, the sidebar's **Running** entry lists it, the running
game window opens on double-click, **Show logs** shows the process output, and
**Stop** ends it. After it exits, the playtime and last-played values are updated
(the **Recent** ordering reflects it).

**If it fails:** right-click → **Show logs** and attach that plus
``$SMOKE/<profile>/home/.cache/lutris/lutris.log``.

Item 5 - Preferences persist (``fresh``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** main menu → **Preferences** ("Lutris settings"). The sidebar has
Interface, Runners, Sources, Accounts, Updates, System, Storage and Global
options. In **Interface** change **Theme** to Dark (or toggle **Hide text under
icons**), close the dialog, quit the client and run ``launch fresh`` again.

**Pass:** the change is visible immediately, still applied after the restart,
and written to ``$SMOKE/fresh/home/.local/share/lutris/lutris.conf``. Switching
the theme back to System Default also works.

Item 6 - Runner configuration (``fresh``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** in the sidebar open **Runners**, double-click **Linux** (or right-click →
**Configure**). Change **Arguments** to something visible, **Save**, then reopen
the dialog.

**Pass:** the dialog reopens with the new value, the reset button next to the
option restores the default, and the value is stored in
``$SMOKE/fresh/home/.local/share/lutris/runners/linux.yml``.

Item 7 - Install from the website (``fresh``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** "Add Game" → **Search the Lutris website for installers** → search for a
small free game (Teeworlds works well) → **Install**, then follow the installer
through to the end.

**Pass:** the installer window opens and shows the steps, the download and
install complete without errors, the game appears in the library with its banner
and cover, and **Play** works. Cancelling a second install half-way leaves no
broken entry behind.

**Offline machine:** skip this item and say so in the report; the automated
checks already cover the installer parser.

Item 8 - Service sync (``existing``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** **Preferences → Sources** (or sidebar → **Sources** → the service), then
**Connect**/**Reload** for the service installed on this machine. Start one
installed service game, then **Reload** again.

**Pass:** the service game list fills in, **Run** launches an installed game, a
second **Reload** does not duplicate entries, **Disconnect** clears them, and the
CLI agrees with the GUI::

    env HOME="$SMOKE/existing/home" \
        XDG_DATA_HOME="$SMOKE/existing/home/.local/share" \
        XDG_CONFIG_HOME="$SMOKE/existing/home/.config" \
        XDG_CACHE_HOME="$SMOKE/existing/home/.cache" \
        LUTRIS_ALLOW_LOCAL_PYTHON_PACKAGES=1 \
        "$REPO/.venv/bin/python" "$REPO/bin/lutris" --list-all-service-games

Item 9 - Shortcuts (``existing``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** right-click a game → **Create desktop shortcut**, then **Create
application menu shortcut**.

**Pass:** both files appear and parse::

    ls "$SMOKE/existing/home/Desktop"
    ls "$SMOKE/existing/home/.local/share/applications"

Each ``.desktop`` file should contain a ``lutris:rungameid/<id>`` URL. Delete
them again with the matching **Delete desktop shortcut** / **Delete application
menu shortcut** entries and check that the files are gone.

Item 10 - Restart and clean shutdown (both profiles)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** quit with Ctrl+Q, relaunch the same profile, then check the profile from
the command line::

    grep -i traceback "$SMOKE"/*/home/.cache/lutris/lutris.log
    python3 -c 'import sqlite3, sys; print(sqlite3.connect(sys.argv[1]).execute("pragma integrity_check").fetchone()[0])' \
        "$SMOKE/fresh/home/.local/share/lutris/pga.db"

**Pass:** the client closes without a crash dialog, reopens with the same
library, the ``grep`` finds nothing, and ``pragma integrity_check`` prints
``ok`` for every tested profile.

Step 5 - Repeat the relevant items on your own profile
------------------------------------------------------

The "existing install" case that matters most is a real one. Back the library up
first, then repeat items 2, 4, 6, 8, 9 and 10 against your own installation::

    cp -a "$HOME/.local/share/lutris/pga.db" "$HOME/.local/share/lutris/pga.db.bak"
    ./bin/lutris -d

Without the sandbox environment variables this opens your real profile, and the
first launch runs any pending migrations once. Note in the report anything that
looks migrated, renamed or missing compared to what you had before.

Step 6 - Tear down
------------------

::

    rm -rf "$SMOKE"

Shortcuts created inside the sandbox disappear with it. Shortcuts created on your
real profile in Step 5 must be deleted from the client (right-click → **Delete
desktop shortcut** / **Delete application menu shortcut**).

Reporting the result
--------------------

Paste this into the release pull request or issue::

    Release smoke test - <version> (<date>)

    Automated    : utils/release-smoke-test.sh -> 53 passed, 0 failed, 0 skipped
    GUI fresh    : 1 ok  3 ok  4 ok  5 ok  6 ok  7 skipped (offline)  10 ok
    GUI existing : 2 ok  4 ok  8 ok  9 ok  10 ok
    Own profile  : 2 ok  4 ok  6 ok  8 ok  9 ok  10 ok

    Notes: ...

Troubleshooting
---------------

- "display checks will be skipped" in the script: there is no session. Run it
  from your desktop, or with ``xvfb-run -a utils/release-smoke-test.sh``.
- "a Lutris instance is already running": close the client, including the tray
  instance, and re-run. This is the single-instance application ID.
- A game does not start: right-click → **Show logs**. The exact command line is
  there, and ``$SMOKE/<profile>/home/.cache/lutris/lutris.log`` has the rest.
- "Creating launcher: unable to find directory for .desktop files": the profile
  has no XDG desktop directory (``~/.config/user-dirs.dirs`` inside the sandbox
  has it disabled). That is an environment problem, not a Lutris bug; skip the
  desktop shortcut half of item 9 and say so in the report.
- The client opens your real library instead of the test profile: the
  environment variables were not applied. Check that ``$SMOKE`` is set and that
  you used ``launch``, not ``bin/lutris``.
- Settings seem not to persist: confirm you are looking at
  ``.local/share/lutris/lutris.conf`` and not at ``~/.config/lutris`` (the
  deprecated location, unused by these profiles).
