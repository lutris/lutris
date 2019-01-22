import gi
NOTIFY_SUPPORT = True
try:
    gi.require_version('Notify', '0.7')
    from gi.repository import Notify
except ImportError:
    NOTIFY_SUPPORT = False
from lutris.util.log import logger

if NOTIFY_SUPPORT:
    Notify.init("lutris")


def send_notification(title, text, file_path_to_icon=""):
    if NOTIFY_SUPPORT:
        notification = Notify.Notification.new(title, text, file_path_to_icon)
        notification.show()
    else:
        logger.info(title)
        logger.info(text)
