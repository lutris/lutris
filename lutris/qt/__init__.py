"""The Qt frontend, built with PySide6 on nothing of the core but its API (lutris.backend).

Qt dispatches events through GLib, so Gio.Application.run() drives Qt, GLib and
asyncio while preserving single-instance command forwarding. See docs/architecture.rst.
"""
