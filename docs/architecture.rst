Architecture
============

Where this is going
-------------------

Lutris is being split into a **core** that knows nothing about any user
interface, and **frontends** that drive it. The GTK interface in
``lutris/gui`` is the only frontend today. The aim is to make a second one, in
Qt through PySide6, a matter of writing widgets rather than untangling
application logic, and eventually to run the core as a separate process, a
server, that several frontends (Qt, a gamepad interface, the command line) can
talk to.

That happens in three stages:

1. **Separate the core in-process.** The core stops importing the GUI and GTK.
   It reports what happens through notifications and asks the user things
   through delegates; the GTK frontend implements both. This is the stage
   that matters most for Qt; only moving the command line out of the GTK
   application is left.
2. **Give the core a front door.** A small API of plain-data calls and events
   (list games, launch, install, log in to a service, ...) that frontends use
   instead of reaching into ``Game``, runner and service objects.
3. **Move the core out of process**, by putting that API behind IPC. It only
   becomes possible once frontends use nothing but the API.

The Qt frontend can start as soon as stage 1 is done, and grows alongside
stage 2.

The rule
--------

**Code outside a frontend package never imports from a frontend, nor a GUI
toolkit.** Concretely, nothing outside ``lutris/gui`` may import
``lutris.gui``, or the ``Gtk``, ``Gdk``, ``GdkPixbuf``, ``GnomeDesktop``,
``WebKit2`` (and similar) introspection namespaces. ``GLib``, ``GObject`` and
``Gio`` are allowed: they aren't UI, and Qt's event loop on Linux is GLib's.
The exception is ``Gio.Application.get_default()``: the running application
belongs to the frontend.

``tests/_test_architecture.py`` enforces this, with no exceptions. The GTK
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
    notifications) runs on the installed ``MainLoop``. The default is GLib's;
    a Qt frontend installs one built on ``QTimer`` with ``set_main_loop()``
    before it starts.

Displays: ``lutris.util.display_backend``
    What only the UI toolkit knows about the screen (whether it's X11, the
    primary monitor's scale, and how to keep the computer awake when no
    screen saver D-Bus interface will) comes from the installed
    ``DisplayBackend``. ``lutris.util.display`` asks it, and prefers Mutter's
    D-Bus interface to it for display modes. The GTK frontend installs
    ``lutris.gui.display_backend.GtkDisplayBackend``, which reads GDK and
    GnomeDesktop; without one, the core reads the environment and uses xrandr.
    A Qt frontend would install one built on ``QScreen``.

Background work: ``lutris.util.jobs``
    ``AsyncCall`` runs a function on a thread and delivers its result on the
    main loop. ``callback_target`` cancels delivery if its object reports being
    destroyed (anything with ``call_when_destroyed``; the GTK frontend adds that
    to widgets, a Qt one would to ``QObject``).

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
    shows an error dialog. A Qt frontend would do the same for its slots.

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

Remaining work for stage 1
--------------------------

Command line
    The command line (``lutris -l``, ``--install``, ``--export`` and so on) is
    handled inside the GTK ``Gtk.Application``. It should become its own small
    frontend over the core, so it works with no GUI toolkit installed.

Stage 2 and 3
-------------

The API's calls and events will carry plain data (ids, dictionaries,
dataclasses), never live ``Game`` or service objects, so that the same API can
later be served over IPC unchanged. Which IPC to use (D-Bus, which Lutris
already uses, or JSON-RPC over a Unix socket) is decided at stage 3, when the
API's shape is known.
