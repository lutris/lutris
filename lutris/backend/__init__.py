"""The backend's front door: the API frontends use to drive Lutris.

Every call is a coroutine that takes and returns plain data (ids, strings,
frozen dataclasses from lutris.backend.models, JSON-like dictionaries), never a
live Game, runner or service object. That's what lets the same API be served
over IPC later, unchanged: a remote frontend would await the same calls. Where
a call needs the user, it takes a delegate (lutris.delegates), as the core
does. See docs/architecture.rst.

The calls run on the frontend's asyncio event loop; anything slow (the network,
large files) goes to a worker thread, so awaiting a call never blocks the UI.
"""
