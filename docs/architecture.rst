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
   through delegates; the GTK frontend implements both. This is the stage in
   progress, and the one that matters most for Qt.
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

``tests/_test_architecture.py`` enforces this. It lists the couplings that
predate the rule, fails on any new one, and fails when a listed one has been
removed but is still listed, so the list only shrinks. That list is also the
to-do list for stage 1.

How the core reaches a frontend
-------------------------------

The core never calls into a frontend directly. These are the ways it gets one
to do something, and new code should use them:

The main loop: ``lutris.util.mainloop``
    All deferred work (``schedule_at_idle``, ``AsyncCall`` callbacks,
    notifications) runs on the installed ``MainLoop``. The default is GLib's;
    a Qt frontend installs one built on ``QTimer`` with ``set_main_loop()``
    before it starts.

Background work: ``lutris.util.jobs``
    ``AsyncCall`` runs a function on a thread and delivers its result on the
    main loop. ``callback_target`` cancels delivery if its object reports being
    destroyed (anything with ``call_when_destroyed``; the GTK frontend adds that
    to widgets, a Qt one would to ``QObject``).

Notifications: ``lutris.util.notifications``
    ``NotificationSource`` is how the core announces that something happened:
    ``GAME_STARTED``, ``GAME_UPDATED``, ``SERVICE_GAMES_LOADED``,
    ``CATEGORIES_UPDATED`` and so on. Handlers always run on the main loop,
    never inline. These are what will become the server's event stream.

Delegates: ``lutris.delegates``
    When the core needs the user (confirm a launch, pick a launch
    configuration, answer an installer question, provide a file, log in to a
    service), it calls a delegate passed in by the caller. The base
    ``Delegate`` has the general questions (``show_notice``, ``ask_question``,
    ``ask_for_text``, ``ask_for_file``); ``LaunchUIDelegate``,
    ``InstallUIDelegate`` and ``ServiceLoginUIDelegate`` add what launching,
    installing and logging in need. The base classes make the non-interactive
    choice; ``lutris.gui.dialogs.delegates`` implements them with GTK dialogs,
    and the main window is the delegate the GTK frontend passes around. A Qt
    frontend would do the same with its own dialogs.

    Operations that take a callback instead of a delegate follow the same
    idea: cloud save sync takes a ``ConflictResolver`` to ask which saves to
    keep, and skips conflicts when given none.

    When the core needs the user and no one asked it to do anything (a
    service's login expiring in the background), it fires a notification
    instead (``SERVICE_LOGIN_REQUIRED``) and a frontend answers it by
    starting the operation with its own delegate.

Models instead of widgets
    When the core produces something a frontend displays as it changes, it
    keeps it in a plain object with a notification, and the frontend adapts
    that to its own widgets. Two examples:

    * ``lutris.util.log_buffer.LogBuffer``: games and installer commands write
      their output to one, and the GTK frontend mirrors it into a
      ``Gtk.TextBuffer`` (``lutris.gui.widgets.log_text_view.mirror_log_buffer``).
    * ``lutris.util.file_downloads``: ``SingleFileDownload`` and
      ``FileCollectionDownload`` run an installer's downloads (queueing,
      retries, the download cache) and publish their progress as
      ``DownloadStatus`` data; ``lutris.gui.widgets.download_progress_box`` only
      displays it. ``ProgressInfo`` (``lutris.util.progress_info``) does the
      same for the sidebar's progress bars.

    Notifications are delivered later, on the main loop, so a model that
    changes quickly should pass a snapshot of its state with each one rather
    than have handlers read its current state (the downloads do).

Remaining work for stage 1
--------------------------

Grouped by what has to be built, roughly in the order planned:

Media
    Services build game artwork with helpers from ``gui/widgets/utils.py`` and
    ``gui/views/media_loader.py``. The parts that only download and process
    images (with Pillow) move into the core; only drawing stays in the GUI.

Errors
    ``exception_backstops.py`` both reports unhandled errors with GTK dialogs
    and wraps GLib callbacks. The reporting moves into the GTK frontend; the
    core announces errors with a notification (``GAME_UNHANDLED_ERROR`` already
    exists).

The game, services and the application object
    ``game.py`` reaches for ``LutrisApplication`` and the main window (to show
    windows, hide on launch, show cloud sync progress), and services open the
    installer window through ``Gio.Application.get_default()``
    (``services/base.py``, ``services/lutris.py``, ``services/ubisoft.py``).
    Those become notifications and delegate calls. The test above doesn't
    catch these, as they go through ``Gio``.

Display information
    ``util/display.py`` reads monitors and resolutions through ``Gdk`` and
    ``GnomeDesktop`` and is used by runners. It needs a small display
    interface the frontend (or a toolkit-free backend such as xrandr)
    provides.

Leftovers
    The installer interpreter's GObject signals become notifications;
    ``startup.py`` stops checking ``GdkPixbuf`` formats; once nothing in the
    core imports GTK, ``lutris/__init__.py`` stops pinning the GTK version and
    the GTK frontend does it instead.

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
