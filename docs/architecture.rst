Architecture
============

Where this is going
-------------------

Lutris is being split into a **core** that knows nothing about any user
interface, and **frontends** that drive it: the GTK interface in
``lutris/gui``, the command line in ``lutris/cli``, and the Qt interface in
``lutris/qt``, built with PySide6, which is replacing the GTK one. The aim is
to run the core as a separate process eventually, a server, that several
frontends (Qt, a gamepad interface, the command line) can talk to.

That happens in three stages:

1. **Separate the core in-process.** The core stops importing the GUI and GTK.
   It reports what happens through notifications and asks the user things
   through delegates; the GTK frontend implements both. This is the stage
   that matters most for Qt, and it's done.
2. **Give the core a front door.** A small API of plain-data calls and events
   (list games, launch, install, log in to a service, ...) that frontends use
   instead of reaching into ``Game``, runner and service objects. This is the
   stage in progress: the API is ``lutris.backend``, and the command line and
   Qt frontends use nothing else.
3. **Move the core out of process**, by putting that API behind IPC. It only
   becomes possible once frontends use nothing but the API.

Stage 2 and the Qt frontend go together. Rather than move the GTK frontend
onto the API, which would mean reworking a great deal of code that's being
replaced anyway, the Qt frontend is built on the API alone, and the API grows
what it needs. The GTK frontend is frozen meanwhile: it keeps working as it is,
and is removed once the Qt one can do everything it does.

The rule
--------

**Code outside a frontend package never imports from a frontend, nor a GUI
toolkit.** Concretely, nothing outside ``lutris/gui`` and ``lutris/cli`` may
import ``lutris.gui`` or ``lutris.cli``, and nothing outside ``lutris/gui``
may import the ``Gtk``, ``Gdk``, ``GdkPixbuf``, ``GnomeDesktop``,
``WebKit2`` (and similar) introspection namespaces. ``GLib``, ``GObject`` and
``Gio`` are allowed: they aren't UI, and Qt's event loop on Linux is GLib's.
The exception is ``Gio.Application.get_default()``: the running application
belongs to the frontend.

``tests/_test_architecture.py`` enforces this, with no exceptions, and checks
that the command-line frontend imports no GUI toolkit either. The GTK
frontend pins the GTK version it uses (``lutris/gui/__init__.py``), and checks
what it needs at startup, such as the image formats GdkPixbuf can load.
``tests/_test_imports.py`` checks that each core module can be imported on its
own, which catches the circular imports that moving code tends to create.

How the core reaches a frontend
-------------------------------

The core never calls into a frontend directly. These are the ways it gets one
to do something, and new code should use them:

The main loop: ``lutris.util.mainloop``
    All deferred work (``schedule_at_idle``, ``AsyncCall`` callbacks,
    notifications) runs on the installed ``MainLoop``. The default is GLib's,
    which both GUI frontends run on (PySide6's Qt dispatches its events through
    GLib); a toolkit that didn't would install its own with
    ``set_main_loop()`` before it starts.

Displays: ``lutris.util.display_backend``
    What only the UI toolkit knows about the screen (whether it's X11, the
    primary monitor's scale, and how to keep the computer awake when no
    screen saver D-Bus interface will) comes from the installed
    ``DisplayBackend``. ``lutris.util.display`` asks it, and prefers Mutter's
    D-Bus interface to it for display modes. The GTK frontend installs
    ``lutris.gui.display_backend.GtkDisplayBackend``, which reads GDK and
    GnomeDesktop; without one, the core reads the environment and uses xrandr.
    The Qt frontend installs ``lutris.qt.display_backend.QtDisplayBackend``,
    which asks Qt's platform plugin and screens.

Background work: ``lutris.util.jobs``
    ``AsyncCall`` runs a function on a thread and delivers its result on the
    main loop. ``callback_target`` cancels delivery if its object reports being
    destroyed (anything with ``call_when_destroyed``; the GTK frontend adds that
    to widgets). Frontends on the backend's API use asyncio tasks instead, and
    cancel them.

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
    choice; ``lutris.gui.dialogs.delegates`` implements them with GTK dialogs,
    and the main window is the delegate the GTK frontend passes around. A Qt
    frontend would do the same with its own dialogs.

    Installing a game goes through the delegate too: ``Game.install()``,
    ``install_updates()``, ``install_dlc()`` and a service's ``install()`` find
    the installer scripts, then hand them to ``start_installer``, which the GTK
    frontend answers by opening its installer window.
    ``lutris.installer.install_from_lutris`` does the same with a game's
    installers from Lutris.net.

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
    callbacks is the frontend's job, as it depends on the toolkit:
    ``lutris.gui.exception_backstops`` wraps GLib's and GObject's callbacks and
    shows an error dialog. The Qt frontend shows the errors that escape its
    slots, which PySide6 passes to ``sys.excepthook``, and those of its tasks
    (``lutris.qt.tasks``).

Models instead of widgets
    When the core produces something a frontend displays as it changes, it
    keeps it in a plain object with a notification, and the frontend adapts
    that to its own widgets. For example:

    * ``lutris.util.log_buffer.LogBuffer``: games and installer commands write
      their output to one, and the GTK frontend mirrors it into a
      ``Gtk.TextBuffer`` (``lutris.gui.widgets.log_text_view.mirror_log_buffer``).
    * ``lutris.services.service_media``: services download game artwork
      with ``download_media`` and process it with Pillow
      (``lutris.util.images``), then fire ``MEDIA_CACHE_INVALIDATED``; frontends
      only load and draw the files.
    * ``lutris.util.file_downloads``: ``SingleFileDownload`` and
      ``FileCollectionDownload`` run an installer's downloads (queueing,
      retries, the download cache) and publish their progress as
      ``DownloadStatus`` data; ``lutris.gui.widgets.download_progress_box`` only
      displays it. ``ProgressInfo`` (``lutris.util.progress_info``) does the
      same for the sidebar's progress bars.

    * ``lutris.services.gog_cloud_operation``: ``start_cloud_sync`` runs a GOG
      game's cloud save sync before it launches and after it quits, in order,
      and announces each ``CloudSyncOperation`` with ``CLOUD_SYNC_STARTED`` and
      ``CLOUD_SYNC_ENDED``; the GTK frontend shows its progress in the sidebar.

    Notifications are delivered later, on the main loop, so a model that
    changes quickly should pass a snapshot of its state with each one rather
    than have handlers read its current state (the downloads do).

The command line
----------------

Every ``lutris`` command starts in ``lutris.cli.application``'s
``CommandLineApplication``, a ``Gio.Application`` with the same id as the GTK
frontend's, so Lutris still runs once:

* A command that needs no GUI (listing games or runners, installing a runner,
  ``--export``, ``-b``, ``-e`` and so on, ``lutris.cli.options.TEXT_COMMANDS``)
  is forwarded to the Lutris instance already running, whatever its frontend,
  and runs there; with none running, it runs in the ``lutris`` process itself,
  with no GUI toolkit loaded. The commands live in ``lutris.cli.commands``,
  which the GTK frontend calls for the command lines forwarded to it. They
  print, ask and resolve relative paths through ``CommandOutput``, so they reach
  the terminal that ran ``lutris`` even when another process runs them.
* Any other command line (no arguments, a ``lutris:`` URI, ``-i``,
  ``--submit-issue``) needs a GUI: ``CommandLineApplication`` exits before
  registering, and ``bin/lutris`` runs the GTK frontend with it instead.

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
``runners``, ``installers`` (finding and checking install scripts),
``installations`` (running them), ``configuration`` (game, runner and system
options),
``processes`` (running a command the way Lutris runs games) and ``saves``.
``lutris.backend.startup.start_backend()`` starts it; that isn't an API call,
but what the backend's own process will do in stage 3.

asyncio runs on GLib's main loop: ``bin/lutris`` calls
``lutris.util.mainloop.run_asyncio_on_glib()``, after which PyGObject runs
asyncio whenever a ``Gio.Application`` (so a ``Gtk.Application`` too) runs.
Frontends start a call with ``Gio.Application.create_asyncio_task()``, which
keeps the application running until it finishes; in the GTK frontend,
``lutris.gui.tasks.start_task()`` does that and shows any error the call
raises, as the exception backstops do for callbacks. A command line handled that
way reports its exit status with ``set_exit_status()`` and ``done()`` (see
``lutris.cli.commands.handle_command_line``). Nested loops such as
``Gtk.Dialog.run()`` still work, but pause asyncio while they run, so new code
shouldn't add any.

PySide6's Qt runs on GLib's main loop too (its event dispatcher is GLib's), so
the Qt frontend is a ``Gio.Application`` like the GTK one:
``Gio.Application.run()`` drives Qt's events, GLib's and asyncio's alike, and
the single instance and command-line forwarding work the same way.
``lutris.qt.tasks.start_task()`` is its counterpart of the GTK one.

``tests/_test_frontend_api.py`` enforces this: a frontend may import
``lutris.backend``, its own package and a few support modules (logging,
strings, settings, notifications, delegates), and nothing else from the core.
The command-line and Qt frontends have no exceptions. Its ``KNOWN_VIOLATIONS``
list is what the frozen GTK frontend uses directly, and only keeps it from
getting worse.

The Qt Quick frontend
---------------------

It's an optional extra while it grows: ``uv sync --extra qt`` installs PySide6,
and ``LUTRIS_FRONTEND=qt`` makes ``bin/lutris`` run it instead of the GTK one.
The Flatpak doesn't include it yet. Its tests run on Qt's offscreen platform.

The frontend uses a PySide6 ``QGuiApplication`` and Qt Quick Controls.
``lutris/qt/qml`` defines the windows, views and dialogs.
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
A shortcut uses the running instance if there is one. On a fresh launch,
``LUTRIS_FRONTEND=qt`` selects Qt as usual. Log updates use ``GAME_LOG_CHANGED`` and ``games.get_game_log``.

Game Actions can move a local installation to another folder, uninstall it,
or remove its library entry. Uninstalling keeps the files and library entry
unless the user selects otherwise. The ``game_maintenance`` backend checks
again before moving or trashing files and blocks protected, overlapping, and
externally managed installations. Qt refreshes the library on ``GAME_CHANGED``
or ``GAME_REMOVED``.

The Library menu can add an existing native Linux executable as a new game.
For an eligible uninstalled entry, Game Actions can link the executable to
that entry and keep its ID, category membership and playtime. The
``local_games`` backend validates the path and writes the launch configuration
before updating the library and firing ``GAME_INSTALLED``. It deliberately
does not record a managed installation directory: Browse Files still opens
the executable's folder, but Move and Trash Files cannot act on it from that entry.
Store-owned entries, non-Linux runners, and installer scripts are not handled
by this flow.

For an uninstalled library entry with a Lutris.net slug, Game Actions can
open its install scripts. ``installers.find_game_installers`` fetches them
off the UI loop and returns an ``InstallerCatalog`` of ``InstallerChoice``
metadata; the scripts stay in the backend under the catalog's id, and
``installers.close_catalog`` drops them when the dialog closes (the backend
also keeps only the most recent few). ``installers.select_installer`` builds a
``ScriptInterpreter`` on a copy of the script in a worker thread, which checks
it, and returns an ``InstallerSelection``: the default folder, the runners
that would be installed first, or the slug of a game that must be installed
before it. The dialog can then show that game's installers. Nothing runs and
no folder is created until the user starts the installation.

``installations.start_installation`` runs a catalog's script into the chosen
folder. It builds a fresh ``ScriptInterpreter`` from the catalog's script with
a backend delegate, and the installation then moves through stages:
preparing (runners, then extras), ``extras``, ``files``, ``downloading``,
``installing`` (the script's commands), ``menu`` and ``disc`` (questions the
script asks), and finally ``finished``, ``failed`` or ``cancelled``. Each
change fires ``INSTALLATION_CHANGED`` with an ``InstallationInfo`` snapshot,
and command output fires ``INSTALLATION_LOG_CHANGED``. Where the script needs
the user, the installation waits in that stage until the frontend answers
(``choose_extras``, ``set_file_source`` and ``start_files``, ``answer_menu``,
``answer_disc``). Runners are installed in worker threads, one after another,
without the shared ``RUNNERS_INSTALLED`` notification. Downloads use
``lutris.util.file_downloads``, three at a time. ``cancel_installation``
reverts, optionally removing the folder the installation created, and
``close_installation`` forgets it and cleans the installer cache. When it
finishes, the backend creates the chosen desktop and menu shortcuts and fires
``GAME_INSTALLED``. Qt's ``InstallerDialog`` shows these stages with
``InstallationPage`` and can launch the game at the end.

Game Actions → Configure, Library → Global Options and a runner's context menu
in the sidebar open configuration forms. ``configuration.open_game_config``,
``open_runner_config`` and ``open_system_config`` build a ``LutrisConfig`` at
that level and return a ``ConfigForm``: a ``ConfigPage`` per config section
(game, runner, system), each with ``ConfigOptionInfo`` rows. The backend
evaluates the option dicts' callables the way GTK's widget generator does, with
the option key and the configuration, so visibility, conditions,
``conditional_on``, choices, warnings and errors arrive as plain values.
``set_option`` and ``reset_option`` change the raw config at the form's level,
checked against the option's type, and return the form evaluated again.
``save_config`` runs the options' validators, writes the file and fires
``GAME_CHANGED`` for a game. Choices loaded in the background (``async_choices``)
fire ``CONFIG_FORM_CHANGED``. A game's form also carries its ``GameDetails``
(name, sort name, slug, runner, year, playtime), changed with
``set_game_details`` and written by ``save_config``, which validates them as
GTK's dialog does and renames the config file when the slug changes.
``set_game_runner`` starts the game's configuration afresh for another runner.
``open_new_game_config`` is Library → Add Game: saving it creates the game.
Qt shows the details on a Game Info tab before the option pages. Qt's ``ConfigOptionModel`` updates rows in place,
so editing doesn't reset the view, and ``ConfigOption.qml`` picks an editor per
option type.

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

What it needs next, roughly in order, each with the backend calls it takes:

* **Game actions** still need service installation entry points. The launch
  configuration prompt receives ``GameInfo`` and configuration names. The
  remaining launch delegate methods still need the same plain-data boundary.
* **Game info leftovers**: the preferred launch configuration reset, and moving
  the game from the Game Info tab (Game Actions → Move already does).
* **Preferences**: the other tabs of GTK's preferences dialog (interface,
  runners, sources, accounts, updates, storage, system info). Global system
  options already work.
* **Services and runners**: logging in (a web view, QtWebEngine), syncing
  libraries, installing and configuring runners.
* **The installer**: service installs (GOG, Steam...), local script files,
  installer URIs, Steam-provided files, and the yes/no and file questions some
  runners ask while installing.
* **The rest of the application** still needs the tray icon,
  runtime updates, and the remaining command-line actions, including installer URIs.

Script installer handoff
~~~~~~~~~~~~~~~~~~~~~~~~

Lutris.net scripts install from Qt end to end (see above). Not handled yet:

* **Steam-provided files** (``$STEAM`` URLs): ``prepare_files`` fails the
  installation with a message. GTK drives them with
  ``lutris.installer.steam_installer.SteamInstaller``, which is toolkit-free
  and can be bridged the way downloads are.
* **Runner questions**: ``_RunnerDelegate`` answers yes to yes/no questions and
  gives no file to file questions, as the base ``InstallUIDelegate`` does. A few
  runners ask for BIOS files this way. Bridge them with
  ``asyncio.run_coroutine_threadsafe`` from the worker thread to a frontend
  prompt, since ``runner.install`` runs in a thread.
* **Runner download progress**: the download is kept so cancelling stops it,
  but its progress isn't reported yet.
* **Service installs**: ``Game.install`` hands store games to
  ``service.install``, which may use its own installers (GOG's ``gogdl``) or
  build a script; that needs the service's login state from the backend first.
* **Local script files and installer URIs**: ``lutris.installer.get_installers``
  already reads files; give the catalog a constructor for them, and route the
  ``lutris:install/...`` command line to the Qt dialog.
* **Updates and DLC** (``InstallationKind``): GTK passes a patch version to
  ``prepare_game_files``.

Keep GTK as the default until Qt reaches parity, and keep using
``InstallerWindow`` only as a reference.

Stage 3
-------

Once frontends use nothing but ``lutris.backend``, it can be put behind IPC
unchanged. Which IPC to use (D-Bus, which Lutris already uses, or JSON-RPC
over a Unix socket) is decided then, when the API's shape is known.
