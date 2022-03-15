from gi.repository import Gio

from lutris.util.log import logger


def send_notification(title, text, file_path_to_icon="lutris"):
    icon_file = Gio.File.new_for_path(file_path_to_icon)
    icon = Gio.FileIcon.new(icon_file)
    notification = Gio.Notification.new(title)
    notification.set_body(text)
    notification.set_icon(icon)

    application = Gio.Application.get_default()
    application.send_notification(None, notification)

    logger.info(title)
    logger.info(text)
