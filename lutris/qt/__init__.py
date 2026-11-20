"""The Qt frontend, built with PySide6 on nothing of the core but its API (lutris.backend).

It's replacing the GTK frontend in lutris/gui, which is frozen as it is meanwhile.
Qt runs on GLib's main loop here, so the frontend is a Gio.Application like the GTK
one: Gio.Application.run() drives Qt's events, GLib's and asyncio's alike, and the
same command-line handling and single instance apply. See docs/architecture.rst.
"""
