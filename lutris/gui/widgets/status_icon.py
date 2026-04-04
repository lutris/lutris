"""Status icon stub - AppIndicator requires GTK 3 and is not compatible with GTK 4."""


def supports_status_icon() -> bool:
    return False


class LutrisStatusIcon:
    """Null object that silently does nothing. AppIndicator/AyatanaAppIndicator
    are GTK 3 libraries and cannot be used with GTK 4."""

    def __init__(self, application):
        self.application = application

    def is_visible(self):
        return False

    def set_visible(self, value):
        pass

    def update_present_menu(self):
        pass
