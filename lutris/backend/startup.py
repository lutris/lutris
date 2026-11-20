"""Starting the backend.

While the backend runs in the frontend's process, the frontend starts it; this is
not an API call, and will be what the backend's own process does once there is one.
"""

from lutris import settings
from lutris.migrations import migrate
from lutris.startup import init_lutris, run_all_checks
from lutris.util.log import logger


def start_backend(run_checks_async: bool) -> None:
    """Open the database, migrating it if needed, and run the startup checks; on a
    worker thread if run_checks_async is set."""
    logger.info("Starting Lutris %s", settings.VERSION)
    init_lutris()
    migrate()
    run_all_checks(async_ops=run_checks_async)
