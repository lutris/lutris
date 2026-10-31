Manual GUI checklist
====================

The automated smoke test (``utils/release-smoke-test.sh``) covers everything that
can be driven from the command line. This page is the part that still has to be
clicked, and it is kept short on purpose:

- **Part A** — about 10 minutes, in the sandbox, on a profile that has never been
  opened. This is the "fresh install" pass.
- **Part B** — about 15 minutes, on your own profile after a backup. This is the
  "existing install" pass.

Items whose area the release cannot touch may be skipped, but say which ones in
the release pull request. The item numbers are stable, so reports stay comparable
between releases.

Prerequisites
-------------

- A desktop session (X11 or Wayland). The GUI items cannot be done headless.
- The checkout with its dependencies installed; see ``CONTRIBUTING.md``. Activate
  the virtualenv first, the commands below use the same interpreter as the script.
- A normal user account; Lutris refuses to start as root.
- Part A does not care whether your own Lutris is running: the script and the
  ``launch()`` helper below use a private D-Bus session, so nothing reaches the
  instance on your desktop. Part B uses your own profile, so use one client at a
  time there.
- Optional, for item 8: a game service (Steam, GOG, Epic, ...) installed and
  logged in on the machine.

Step 1 - Run the automated part and keep the sandbox
----------------------------------------------------

The profiles used below are built by the script, inside a temporary directory that
it deletes on exit. Pass ``--keep`` so it survives::

    ./utils/release-smoke-test.sh --keep

When it finishes, the script prints the sandbox path and a ``launch()`` function
that opens the client with each profile. Keep that terminal.

Do not start the GUI pass after a failed automated check: fix that first, the GUI
checks will not tell you anything new about it.

Step 2 - What is inside the sandbox
-----------------------------------

::

    $SMOKE/
      first-run/                 used by Part A
        home/                    empty HOME: a genuine first start
        games/                   fake-game.sh and sleepy.sh, the test executables
      fresh/                     automated scenario: first start, one seeded game
        home/  games/  logs/
      existing/                  automated scenario: upgraded, two seeded games
      clone/                     only with --existing-profile

``first-run``
    Never opened by the automated checks. Part A runs here, so item 1 really is a
    first start: empty library, runtime download, default services.

``fresh``, ``existing``, ``clone``
    Built and used by the automated checks. They are kept so you can look at what
    a check saw, and are not part of the manual pass.

Settings live in ``$SMOKE/<profile>/home/.local/share/lutris/lutris.conf``;
``~/.config/lutris`` is the deprecated location and is not used by these profiles.

Step 3 - Open a sandbox profile
-------------------------------

Never launch ``bin/lutris`` bare for Part A: that opens your real profile. The
script prints this snippet, ready to paste (``$REPO`` is your checkout)::

    SMOKE=/tmp/lutris-smoke.XXXXXXXX
    REPO=/path/to/lutris                 # your checkout
    launch() {
        env HOME="$SMOKE/$1/home" \
            XDG_DATA_HOME="$SMOKE/$1/home/.local/share" \
            XDG_CONFIG_HOME="$SMOKE/$1/home/.config" \
            XDG_CACHE_HOME="$SMOKE/$1/home/.cache" \
            LUTRIS_ALLOW_LOCAL_PYTHON_PACKAGES=1 \
            dbus-run-session -- "$REPO/.venv/bin/python" "$REPO/bin/lutris" -d
    }

    launch first-run

Notes:

- ``dbus-run-session`` is not optional. Only ``--version`` is answered by the
  process you start; every other command line goes over D-Bus to the primary
  instance of ``net.lutris.Lutris``, whichever profile it happens to use. The
  private session is what keeps Part A out of your own library.
- Drop ``-d`` to see the client the way a normal user would; keep it while
  testing, it is what makes a failure diagnosable.
- The log of that client is
  ``$SMOKE/first-run/home/.cache/lutris/lutris.log``.
- Start over with: ``rm -rf $SMOKE`` and re-run the script with ``--keep``.

Part A - a genuine first run (sandbox, ~10 minutes)
---------------------------------------------------

Items 1, 3, 4, 5, 6 and 10. All of this happens on ``first-run``, which has never
been opened, so anything unexpected is a real finding.

Item 1 - First start
~~~~~~~~~~~~~~~~~~~~

**Do:** ``launch first-run``.

**Pass:** the window opens within a few seconds. The header bar has a search entry
("Search games"), an "Add Game" button, a view toggle and the main menu. The
sidebar shows **Library** (Games, Recent, Favorites, Uncategorized, Hidden,
Missing, Running) followed by **Categories**, **Sources**, **Runners** and
**Platforms**. The library is empty. Lutris starts fetching its runtime/DXVK
components, which is normal on a first run. No error dialog.

Anything already in this library means a profile was reused, not a first start.

**If it fails:** attach ``$SMOKE/first-run/home/.cache/lutris/lutris.log`` and the
console output of the launch.

Item 3 - Add a locally installed game
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** "Add Game" → **Add locally installed game** → **Continue**. Name it
``GUI Smoke Test``, set **Runner** to ``Linux``, open the **Game options** tab and
set **Executable** to ``$SMOKE/first-run/games/sleepy.sh``, then **Save**. Reopen
the game with right-click → **Configure** → **Game options**, set **Arguments** to
``--smoke`` and save again.

**Pass:** the dialog closes and the game appears in the library. After quitting and
running ``launch first-run`` again it is still there, and the arguments are still
set — which is the game-level option check::

    grep args "$SMOKE"/first-run/home/.local/share/lutris/games/*.yml

``sleepy.sh`` is a two-line script that sleeps for 30 seconds; item 4 needs a game
that stays running for a moment.

Item 4 - Play from the GUI and stop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** double-click the game.

**Pass:** the game starts, the sidebar's **Running** entry lists it, the running
game window opens on double-click, **Show logs** shows the process output, and
**Stop** ends it. Once it exits, the playtime and last-played values are updated,
which shows in the **Recent** ordering.

**If it fails:** right-click → **Show logs** and attach that plus
``$SMOKE/first-run/home/.cache/lutris/lutris.log``.

Item 5 - Preferences persist
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** main menu → **Preferences** ("Lutris settings"); the sidebar has Interface,
Runners, Sources, Accounts, Updates, System, Storage and Global options. Under
**Interface** set **Theme** to Dark, close the dialog, quit the client with Ctrl+Q
and run ``launch first-run`` again.

**Pass:** the theme is applied immediately and still applied after the restart, and
it is recorded in ``$SMOKE/first-run/home/.local/share/lutris/lutris.conf``.
Switching back to System Default also works.

Item 6 - Runner configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** in the sidebar open **Runners**, then right-click **Wine** → **Configure**.
(Double-clicking a runner row only filters the list; the configuration dialog is in
the context menu.) Untick **Enable DXVK** and save.

**Pass:** the value is written to the runner configuration and survives reopening
the dialog; the reset button next to the option restores the default::

    cat "$SMOKE"/first-run/home/.local/share/lutris/runners/wine.yml

The file should contain ``wine:`` and ``dxvk: false``. The Linux runner has no
runner-level options (its Arguments field is a *game* option, covered by item 3),
so this item uses Wine.

Item 10 - Restart and clean shutdown
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** quit with Ctrl+Q, relaunch the same profile, then check the profile from
the command line::

    grep -i traceback "$SMOKE"/first-run/home/.cache/lutris/lutris.log
    python3 -c 'import sqlite3, sys; print(sqlite3.connect(sys.argv[1]).execute("pragma integrity_check").fetchone()[0])' \
        "$SMOKE/first-run/home/.local/share/lutris/pga.db"

**Pass:** the client reopens with the same library and settings, the ``grep`` finds
nothing, and ``pragma integrity_check`` prints ``ok``.

That is the end of Part A. Tear down this client (Ctrl+Q) before starting Part B.

Part B - your own install (own profile, ~15 minutes)
----------------------------------------------------

Items 2, 7, 8 and 9. This is the "existing install" pass, and it is the only place
where services and a real library can be exercised.

Step B1 - Back up the whole profile
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The migrations rewrite ``lutris.conf`` and ``games/*.yml``, and
``migration_version`` never goes back down, so going back to the installed release
means restoring all of it, not just the database. Skip the runner and runtime
downloads, which are large and untouched::

    tar -C ~/.local/share --exclude='lutris/runners/*' --exclude='lutris/runtime/*' \
        -cJf ~/lutris-profile-backup.tar.xz lutris
    [ -d ~/.config/lutris ] && tar -C ~/.config -cJf ~/lutris-config-backup.tar.xz lutris

Step B2 - Open your profile
~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    ./bin/lutris -d

No environment variables this time: this is your real profile. The first launch of
a new build runs any pending migrations once, which is what the backup above is for.

Item 2 - Library rendering
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** in your own library, type something into "Search games" and clear it;
switch views with "Toggle View"; click **Recent**, **Games**, and a category;
right-click a game → **Categories**, add a category, save.

**Pass:** the library renders with its banners and cover art, scrolling is smooth,
search narrows and restores the list, both views work, the sidebar counts match,
and the category survives a restart.

**If it fails:** note which entry is missing or misrendered and what triggered it.

Item 7 - Install from the website (only if the release can affect installers)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** "Add Game" → **Search the Lutris website for installers** → pick any small
installer that works today, install it end to end, then remove it.

**Pass:** the installer window opens and shows its steps, the download and install
finish, the game appears with its media and **Play** works.

**If it fails:** run the same installer with the previous release before calling it
a blocker. A broken installer on lutris.net or a dead mirror is not a client
regression.

**Skip it** with a note when the release does not touch the installer, download or
media code.

Item 8 - Service sync (only if the release can affect services)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** **Preferences → Sources** (or sidebar → **Sources** → the service),
**Connect**/**Reload** a service installed on this machine, start one installed
service game, then **Reload** again.

**Pass:** the service game list fills in, **Run** launches a game, a second
**Reload** does not duplicate entries, and **Disconnect** clears them. The command
line agrees, on your real profile::

    ./bin/lutris --list-all-service-games

**Skip it** with a note when the release does not touch service code. It cannot be
done in the sandbox: Steam is looked up under ``~/.steam`` and the other services
need a login inside the sandbox.

Item 9 - Shortcuts, then revert
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:** right-click a game → **Create desktop shortcut**, then **Create application
menu shortcut**.

**Pass:** both files exist and contain a ``lutris:rungameid/`` URL::

    ls ~/Desktop
    ls ~/.local/share/applications

**Revert:** use the matching **Delete desktop shortcut** and **Delete application
menu shortcut** entries. These are real files in your profile, so do not leave them
behind.

Step B3 - Restore if something looks wrong
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Quit the client, then restore whichever backup you took::

    tar -C ~/.local/share -xJf ~/lutris-profile-backup.tar.xz
    [ -f ~/lutris-config-backup.tar.xz ] && tar -C ~/.config -xJf ~/lutris-config-backup.tar.xz

Step 4 - Tear down
------------------

::

    rm -rf "$SMOKE"
    rm -f ~/lutris-profile-backup.tar.xz ~/lutris-config-backup.tar.xz

Reporting the result
--------------------

Paste this into the release pull request or issue, with the counts from your run::

    Release smoke test - <version> (<date>)

    Automated : utils/release-smoke-test.sh -> <N> passed, <M> failed, <K> skipped
    Part A (sandbox, first run) : 1 ok  3 ok  4 ok  5 ok  6 ok  10 ok
    Part B (own profile)        : 2 ok  9 ok   7 skipped (no installer changes)
                                               8 skipped (no service changes)

    Notes: ...

Troubleshooting
---------------

- "display checks will be skipped" from the script: there is no session. Run it
  from your desktop, or with ``xvfb-run -a utils/release-smoke-test.sh``.
- "the client shows my own library during Part A": the environment variables were
  not applied, or ``launch`` was not used. Check that ``$SMOKE`` is set.
- A game does not start: right-click → **Show logs**. The exact command line is
  there, and ``$SMOKE/<profile>/home/.cache/lutris/lutris.log`` has the rest.
- "Creating launcher: unable to find directory for .desktop files": the XDG desktop
  directory is disabled in that profile. Skip the desktop half of item 9 and say so.
- Settings seem not to persist: look at ``.local/share/lutris/lutris.conf``, not at
  ``~/.config/lutris`` (the deprecated location, unused by these profiles).
