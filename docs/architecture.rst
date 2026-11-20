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
``runners``, ``processes`` (running a command the way Lutris runs games) and
``saves``.
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

The Qt frontend
---------------

It's an optional extra while it grows: ``uv sync --extra qt`` installs PySide6,
and ``LUTRIS_FRONTEND=qt`` makes ``bin/lutris`` run it instead of the GTK one.
The Flatpak doesn't include it yet. Its tests run on Qt's offscreen platform.

So far it shows the library: a sidebar of views (``library.list_categories``
and the rest), the games of the selected one with search, the installed filter
and sorting, refreshed as ``lutris.backend.events`` report changes, and it
launches and stops games (``games.launch_game`` and ``games.stop_game``; the
backend keeps the running games). Its delegate asks questions with Qt dialogs.

What it needs next, roughly in order, each with the backend calls it takes:

* **Media**: covers and banners, so the library can be a grid like GTK's.
* **Game actions**: install, uninstall, categories, shortcuts, moving a game,
  showing its logs (events carrying ``LogBuffer`` content), and launch
  configurations; delegate methods then receive ``GameInfo`` rather than a
  ``Game``.
* **Configuration**: game, runner and system options, as data, with a widget
  generator like ``lutris/gui/config``.
* **Services and runners**: logging in (a web view, QtWebEngine), syncing
  libraries, installing and configuring runners.
* **The installer**: starting an installation, its questions as delegate calls,
  its progress and downloads as events.
* **Preferences** and the rest of the application: the tray icon, runtime
  updates, and the command-line URIs (``lutris:rungame/...``).

Stage 3
-------

Once frontends use nothing but ``lutris.backend``, it can be put behind IPC
unchanged. Which IPC to use (D-Bus, which Lutris already uses, or JSON-RPC
over a Unix socket) is decided then, when the API's shape is known.
