# Third Party Libraries
import gi

# Lutris Modules
from lutris.util.log import logger

NOTIFY_SUPPORT = True
try:
    gi.require_version('Notify', '0.7')
    from gi.repository import Notify
except ImportError:
    NOTIFY_SUPPORT = False

if NOTIFY_SUPPORT:
    Notify.init("lutris")
else:
    logger.warning("Notifications are disabled, please install" " GObject bindings for 'Notify' to enable them.")


def send_notification(title, text, file_path_to_icon="lutris"):
    if NOTIFY_SUPPORT:
        notification = Notify.Notification.new(title, text, file_path_to_icon)
        notification.show()
    else:
        logger.info(title)
        logger.info(text)
