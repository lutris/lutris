Architecture
============

Where this is going
-------------------

Lutris has a toolkit-independent **core** and two **frontends**: the command
line (``lutris/cli``) and the Qt Quick desktop application (``lutris/qt``).
Both drive the core through ``lutris.backend``, an in-process API of plain-data
calls and events. The GTK frontend has been removed. A future stage could put
the same API behind IPC so the core can run as a separate process.

The rule
--------

**The core never imports a frontend or a GUI toolkit.** ``GLib``, ``GObject``
and ``Gio`` aren't UI and are allowed; accessing the running application
through ``Gio.Application.get_default()`` stays in the frontend.
``tests/_test_architecture.py`` also keeps the CLI toolkit-free and guards the
Qt Quick boundary. The only Qt Widgets imports are ``QApplication`` for
bootstrap and ``QSystemTrayIcon`` and ``QMenu`` for the native system tray.
``tests/_test_imports.py`` checks that each core module can be imported on its
own, which catches the circular imports that moving code tends to create.

How the core reaches a frontend
-------------------------------

The core never calls into a frontend directly. These are the ways it gets one
to do something, and new code should use them:

The main loop: ``lutris.util.mainloop``
    All deferred work (``schedule_at_idle``, ``AsyncCall`` callbacks,
    notifications) runs on the installed ``MainLoop``. The default is GLib's,
    which the Qt and CLI frontends both use; a toolkit that didn't would install its own with
    ``set_main_loop()`` before it starts.

Displays: ``lutris.util.display_backend``
    What only the UI toolkit knows about the screen (whether it's X11, the
    primary monitor's scale, and how to keep the computer awake when no
    screen saver D-Bus interface will) comes from the installed
    ``DisplayBackend``. ``lutris.util.display`` asks it, and prefers Mutter's
    D-Bus interface for Wayland display modes. On X11, the fallback is xrandr.
    ``lutris.qt.display_backend.QtDisplayBackend`` reads Qt's platform and
    screen properties and uses available session services to inhibit sleep.

Background work: ``lutris.util.jobs``
    ``AsyncCall`` runs a function on a thread and delivers its result on the
    main loop. ``callback_target`` cancels delivery if its object reports being
    destroyed (anything with ``call_when_destroyed``). Frontends on the
    backend's API use asyncio tasks instead, and cancel them.

Notifications: ``lutris.util.notifications``
    ``NotificationSource`` is how the core announces that something happened:
    ``GAME_STARTED``, ``GAME_UPDATED``, ``SERVICE_GAMES_LOADED``,
    ``CATEGORIES_UPDATED``, ``RUNNERS_INSTALLED`` (fired with the installer
    interpreter that installed them) and so on. Handlers always run on the main loop,
    never inline. These are what will become the server's event stream.

Delegates: ``lutris.delegates``
    When the core needs the user (confirm a launch, pick a launch
    configuration, answer an installer question, provide a file, log in to a
    service), it calls a delegate passed in by the caller. The base
    ``Delegate`` has the general questions (``show_notice``, ``ask_question``,
    ``ask_for_text``, ``ask_for_file``, and ``start_installer`` to run an
    installer script with the user); ``LaunchUIDelegate``,
    ``InstallUIDelegate`` and ``ServiceLoginUIDelegate`` add what launching,
    installing and logging in need. The base classes make the non-interactive
    choice. Qt handles launch questions with ``PromptController`` and QML.
    Installer questions use plain-data snapshots and responses from
    ``lutris.backend.installations``.

    A game keeps the delegate it was launched with until it quits, for the
    questions that come after the launch: syncing GOG cloud saves asks it which
    saves to keep through ``resolve_cloud_sync_conflict`` (a
    ``ConflictResolver``), and skips conflicts when given none.

    When the core needs the user and no one asked it to do anything (a
    service's login expiring in the background), it fires a notification
    instead (``SERVICE_LOGIN_REQUIRED``) and a frontend answers it by
    starting the operation with its own delegate.

Errors
    The core doesn't show errors. A game's operations are wrapped in
    ``lutris.game_errors.watch_game_errors``, which stops the game and reports
    the error through the game's ``game_error`` or, when nothing handles that,
    the ``GAME_UNHANDLED_ERROR`` notification. Catching what escapes event-loop
    callbacks is the frontend's job. Qt reports errors from its slots through
    ``sys.excepthook`` and from its tasks through ``lutris.qt.tasks``.

Models instead of widgets
    When the core produces something a frontend displays as it changes, it
    keeps it in a plain object with a notification, and the frontend adapts
    that to its own widgets. For example:

    * ``lutris.util.log_buffer.LogBuffer``: games and installer commands write
      their output to one; Qt reads it through the game and installation APIs.
    * ``lutris.services.service_media``: services download game artwork
      with ``download_media`` and process it with Pillow
      (``lutris.util.images``), then fire ``MEDIA_CACHE_INVALIDATED``; frontends
      only load and draw the files.
    * ``lutris.util.file_downloads``: ``SingleFileDownload`` and
      ``FileCollectionDownload`` run an installer's downloads (queueing,
      retries, the download cache) and publish their progress as
      ``DownloadStatus`` data, which the backend exposes to Qt in the
      installation snapshot.

    * ``lutris.services.gog_cloud_operation``: ``start_cloud_sync`` runs a GOG
      game's cloud save sync before it launches and after it quits, in order,
      and announces each ``CloudSyncOperation`` with ``CLOUD_SYNC_STARTED`` and
      ``CLOUD_SYNC_ENDED``. ``lutris.backend.cloud_saves`` exposes transfer
      progress and skipping. Closing the window doesn't interrupt a post-exit
      transfer.

    Notifications are delivered later, on the main loop, so a model that
    changes quickly should pass a snapshot of its state with each one rather
    than have handlers read its current state (the downloads do).

The command line
----------------

Every ``lutris`` command starts in ``lutris.cli.application``'s
``CommandLineApplication``, a ``Gio.Application`` with the same id as the Qt
frontend's, so Lutris still runs once:

* A command that needs no GUI (listing games or runners, installing a runner,
  ``--export``, ``-b``, ``-e`` and so on, ``lutris.cli.options.TEXT_COMMANDS``)
  is forwarded to the Lutris instance already running, whatever its frontend,
  and runs there; with none running, it runs in the ``lutris`` process itself,
  with no GUI toolkit loaded. The commands live in ``lutris.cli.commands``,
  which the Qt frontend calls for the command lines forwarded to it. They
  print, ask and resolve relative paths through ``CommandOutput``, so they reach
  the terminal that ran ``lutris`` even when another process runs them.
* Any other command line (no arguments, a ``lutris:`` URI,
  ``--submit-issue``) needs a GUI: ``CommandLineApplication`` exits before
  registering, and the launcher runs the Qt frontend with it instead.

Both frontends define the same options (``lutris.cli.options``), as Gio
forwards a command line with its options already parsed.

Stage 2: the backend's API
--------------------------

``lutris.backend`` is the front door. Frontends drive Lutris through it, and
eventually through nothing else:

* **Every call is a coroutine** (``await games.list_games()``). Over IPC each
  call becomes a request and its reply, so a remote frontend will await the same
  calls with the same signatures. Calls run on the frontend's asyncio event
  loop, and send slow work (the network, large files) to a thread with
  ``asyncio.to_thread``, so awaiting one never blocks the UI.
* **Calls take and return plain data**: ids, strings, JSON-like dictionaries,
  and the frozen dataclasses in ``lutris.backend.models`` (``GameInfo``,
  ``ServiceGameInfo``, ...), never a live ``Game``, runner or service object.
* **Errors are** ``LutrisError`` **subclasses** (``lutris.backend.errors``), whose
  message is meant for the user.
* **Calls that need the user take a delegate**, as the core does.
* **Events carry plain data too**: ``lutris.backend.events`` re-announces the
  core's game notifications with a ``GameInfo`` (``GAME_CHANGED``,
  ``GAME_INSTALLED``, ``GAME_LAUNCHING``, ``GAME_STARTED``, ``GAME_STOPPED``)
  or a game's id (``GAME_LAUNCH_STATUS``, ``GAME_FAILED``). A launch is
  followed by ``GAME_STARTED`` or ``GAME_STOPPED`` whatever happens, so a
  frontend tracks a game's state from these instead of asking a ``Game``. Over
  IPC they become the server's event stream.

It's grouped by subject: ``games``, ``library`` (what the library's views
list: ``query_games`` takes a ``LibraryQuery``, the view's sidebar row, search
and sort, and returns ``LibraryGame`` rows), ``services``, ``steam``,
``runners``, ``installers`` (preparing and checking installation plans),
``installations`` (running them), ``configuration`` (game, runner and system
options),
``processes`` (running a command the way Lutris runs games) and ``saves``.
``lutris.backend.startup.start_backend()`` starts it; that isn't an API call,
but what the backend's own process will do in stage 3.

asyncio runs on GLib's main loop: ``lutris.launcher`` calls
``lutris.util.mainloop.run_asyncio_on_glib()``, after which PyGObject runs
asyncio whenever a ``Gio.Application`` runs. Qt dispatches its events through
GLib too, so ``Gio.Application.run()`` drives Qt, GLib and asyncio.
``lutris.qt.tasks.start_task()`` uses ``Gio.Application.create_asyncio_task()``
to keep the application running while a call finishes and surface errors.
Forwarded commands report their status with ``set_exit_status()`` and ``done()``.

``tests/_test_frontend_api.py`` enforces this: a frontend may import
``lutris.backend``, its own package and a few support modules (logging,
strings, settings, notifications, delegates), and nothing else from the core.
Qt can also import the shared command handling in ``lutris.cli``. The CLI
must not import Qt.

The Qt Quick frontend
---------------------

PySide6 Essentials is a required dependency in source installs and the Flatpak.
The tests run on Qt's offscreen platform.

The frontend uses Qt Quick Controls and a PySide6 ``QApplication`` so it can
integrate with the native system tray.
``lutris/qt/qml`` defines the windows, views and dialogs.
Every control is drawn by ``LutrisStyle`` (``lutris/qt/qml/LutrisStyle``), a
Qt Quick Controls style that ``MainWindow`` selects with ``QQuickStyle`` before
loading QML, so plain ``import QtQuick.Controls`` gets the Lutris look. Its
``Theme`` singleton holds the colors, metrics and type sizes for light and dark,
following the theme preference and, for "System Default", the desktop's color
scheme. ``Theme.icon()`` names an SVG of the style's icon set, and ``Icon`` draws
one tinted to the text around it. Views reach for ``Theme`` rather than literal
colors, so both themes stay consistent.

The window has a sidebar of library views, a header with search, the installed
filter, sorting, the layout switcher, the **Add** menu and the main menu, and a
bar under the library for the selected game, with Play, Stop or Install and its
Game Actions menu (also on right-click).
``LibraryController`` exposes Qt properties, model roles and slots to QML.
It queries the backend, handles its events, and translates launch prompts
into QML dialogs. QML strings use the application's gettext catalogs.

The library has search, sorting, an installed filter, and sidebar views
including categories, sources and saved searches. It launches and stops games
through the backend. The Game Actions menu can add or remove favorites, hide
or unhide a game, edit its categories, and open its installation directory.
It also shows live game logs and manages desktop, application menu, and Steam
shortcuts. The Steam Big Picture (Standalone) destination exports an executable
script for the selected launch configuration and adds it to Steam separately
from the regular shortcut. The script launches without Lutris; recreate the
shortcut after changing the launch configuration. Qt can remove legacy
standalone entries without deleting their old shared scripts. Standalone
creation is not offered from inside Flatpak because exported commands can refer
to sandbox-only paths.

When a game has multiple launch configurations, Qt can prompt for one and
remember the choice. ``lutris:rungame/...`` and ``lutris:rungameid/...``
launch installed library games, including the launch target encoded in a shortcut.
A shortcut uses the running instance if there is one. Log updates use
``GAME_LOG_CHANGED`` and ``games.get_game_log``.

Game Actions can move a local installation to another folder, uninstall it,
or remove its library entry. Uninstalling keeps the files and library entry
unless the user selects otherwise. The ``game_maintenance`` backend checks
again before moving or trashing files and blocks protected, overlapping, and
externally managed installations. Qt refreshes the library on ``GAME_CHANGED``
or ``GAME_REMOVED``.

The Add menu can add an existing native Linux executable as a new game.
For an eligible uninstalled entry, Game Actions can link the executable to
that entry and keep its ID, category membership and playtime. The
``local_games`` backend validates the path and writes the launch configuration
before updating the library and firing ``GAME_INSTALLED``. It deliberately
does not record a managed installation directory: Browse Files still opens
the executable's folder, but Move and Trash Files cannot act on it from that entry.
Store-owned entries, non-Linux runners, and installer scripts are not handled
by this flow.

Game Actions → Install works on synced source rows, including those that
have yet to be added to the local library. ``installers.find_store_installers``
asks the source for its plans in a worker thread and returns an
``InstallerCatalog`` of ``InstallerChoice`` metadata. GOG offers Update or Repair and Install DLC for installed games,
and itch.io offers updates. Library → Run
Windows Setup uses ``prepare_windows_setup`` to run a local executable with
Wine/Proton and the selected Windows version and locale. Lutris.net installer links and uploaded
YAML installers have been removed. ``lutris:install/<source>:<app-id>`` opens
the same store installer.

Plans stay in the backend until ``close_catalog``. ``select_installer``
checks a copy in a worker thread and returns the default folder, any
required runners, and any missing dependency. ``start_installation``
prepares runners, extras and files, then calls the interpreter. Updates and
DLC use the selected installed game's ID and directory. A cancelled update
or DLC install preserves the base game directory.

Each stage fires ``INSTALLATION_CHANGED`` with an ``InstallationInfo``
snapshot. The frontend responds to runner and interpreter questions with
``answer_runner``, ``choose_extras``, ``set_file_source``,
``start_files``, ``answer_menu`` or ``answer_disc``. File downloads
run three at a time. For Steam data, Lutris requests the install through
Steam and waits for its appmanifest to report a complete installation.
Cancelling that wait leaves Steam's own installation in progress.
``InstallationPage`` shows progress and command output, and completion
fires ``GAME_INSTALLED``. New installs can create shortcuts and launch the
game from the dialog.

Game Actions → Configure, the main menu's Global Options and a runner's context menu
in the sidebar open configuration forms. ``configuration.open_game_config``,
``open_runner_config`` and ``open_system_config`` build a ``LutrisConfig`` at
that level and return a ``ConfigForm``: a ``ConfigPage`` per config section
(game, runner, system), each with ``ConfigOptionInfo`` rows. The backend
evaluates the option dicts' callables with
the option key and the configuration, so visibility, conditions,
``conditional_on``, choices, warnings and errors arrive as plain values.
``set_option`` and ``reset_option`` change the raw config at the form's level,
checked against the option's type, and return the form evaluated again.
``save_config`` runs the options' validators, writes the file and fires
``GAME_CHANGED`` for a game. Choices loaded in the background (``async_choices``)
fire ``CONFIG_FORM_CHANGED``. A game's form also carries its ``GameDetails``
(name, sort name, slug, runner, year, playtime), changed with
``set_game_details`` and written by ``save_config``, which validates them and
renames the config file when the slug changes.
``set_game_runner`` starts the game's configuration afresh for another runner.
``open_new_game_config`` is Add → Add Game: saving it creates the game.
Qt shows the details on a Game Info tab before the option pages. Qt's ``ConfigOptionModel`` updates rows in place,
so editing doesn't reset the view, and ``ConfigOption.qml`` picks an editor per
option type.

For native Linux games, Runner Options → Steam Linux Runtime takes effect
for the game or as the Linux runner's default. None uses the system libraries.
The other choices use Valve's 1.0 (Scout), 2.0 (Soldier), 3.0 (Sniper), or 4.0
container. Lutris finds the launchers in Steam libraries or in umu's runtime
directory. Scout uses the Steam compatibility tool inside Soldier. If a
runtime is missing, the launch error gives its Steam install URI. The runner
applies the choice to primary and alternate launch configurations, including
standalone shortcuts.

The dedicated Flatpak runner and Flathub game source have been removed.
Existing library records can still be removed without changing the installed
apps.

Runtime updates run in the backend (``runtime_updates.update_runtime``), which
announces each component's progress with ``RUNTIME_UPDATE_CHANGED``. Qt runs
them at startup when the last check is stale, shows their progress in the status
bar, and Preferences → Updates checks again on request.

The library opens in a cover grid. The View menu switches to banners or a list
and remembers the choice. Grid queries ask for ``LibraryArtwork`` with each
row. The backend resolves files from the Lutris and service caches. The same
menu downloads missing artwork with ``media.update_artwork``, which Qt also
runs quietly at startup. The grid reloads its thumbnails when it receives
``ARTWORK_CHANGED``.

``lutris.artwork`` fills in each library game's cover, banner and icon (the
``coverart``, ``banners`` and icon files the library reads by slug). It asks the
game's store first: Steam's 2:3 library capsule and header, Epic's tall and wide
box art, GOG's vertical cover from its public game database and its product
image, and for other services the largest portrait and landscape formats their
media classes know. SteamGridDB fills in what's left, and serves games that come
from no store: it's searched by Steam app id or by name, for 2:3 grids (600x900,
or its near 2:3 sizes) and 920x430-shaped ones, and for icons. SteamGridDB needs
the user's API key, saved through ``media.set_steamgriddb_api_key`` (which checks
it first) or given in ``LUTRIS_STEAMGRIDDB_API_KEY``; View → Artwork Sources in
Qt sets it. Only missing files are downloaded, so custom artwork is never
replaced, and what no source has is remembered for a week in
``artwork-misses.json``, kept apart for with and without SteamGridDB, so that adding
a key retries at once.

The Game Info tab also shows the game's own cover, banner and icon
(``game_artwork``). Choosing a file prepares it in Qt: ``QImage`` loads and
scales it down to the size it's stored at off the GUI thread (``QPixmap`` only
works on it) and saves PNG or JPEG, which ``set_custom_artwork`` stores.
``list_steamgriddb_artwork`` and ``use_artwork_url`` offer SteamGridDB's images
to choose from. Chosen artwork is marked custom in the library, so it stays,
and ``reset_artwork`` removes it, forgets past misses and fetches the automatic
artwork again.

Game Info also resets the remembered launch configuration and opens Move for
managed installations. Launching waits for a pending runtime update and can
prompt for a missing runner. GOG cloud conflicts prompt only when a window is
available; otherwise the conflict is skipped rather than silently overwritten.

Library → Preferences includes the interface theme, tray, game card labels and
badges, Discord presence and minimize-on-launch options. The tray is available
only on desktops that provide one. Library also offers checksum-based ROM
registration from a selected folder or files dropped onto the window, without
moving or owning the ROM files. It also offers Playtron import and a local JSON
issue report exporter shared with ``--submit-issue``.

Preferences → Runners uses ``lutris.backend.runners`` to configure, install
and remove runners. Downloads and runner file prompts pass progress and plain
text back to Qt while installation runs in a worker thread. Wine's **Manage
GE-Proton** lists installed builds and recent releases for the host architecture
from GitHub. It reuses the existing SHA-512 verification and installs into
Steam's ``compatibilitytools.d`` directory. The remove action moves builds
from that directory to the Trash. Other Proton locations are listed without a
remove action. GE-Proton (Latest) is still managed by umu at launch.

Selecting a source in Qt exposes **Sign In**, **Sync Library**, and
**Disconnect** as appropriate. Sign-in uses the system default browser.
Amazon and ZOOM Platform accept their redirect URL. Epic Games accepts
its authorization code or the JSON from the final page. itch.io uses a
dedicated API key. GOG uses the redirect URL for its API token and cookies
for the library endpoint. EA App, Humble Bundle, Steam Families, Game Jolt
and DLsite use a user-selected Netscape ``cookies.txt`` export. Lutris
keeps only cookies from the selected store's domain. ``store_login`` retains the service instance
until the handoff completes so it can keep transient login data such as
Amazon's PKCE verifier. The frontend syncs the library on successful
sign-in. ``services`` also supports manual sync for local sources.
Ubisoft Connect can reuse saved credentials or accept a manual browser handoff:
paste ``PRODloginData`` if it contains the session fields, or a JSON array of
``PRODloginData``, ``PRODrememberMe`` and ``PRODlastProfile`` (``null`` for
missing values). Lutris verifies the session before saving it. Treat these
values like passwords. For sources with a separate game launcher, the preferred
registered launcher is used for both opening the store and its new install plans.
