from gettext import gettext as _

from gi.repository import Gdk, Gtk

from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.widgets.log_text_view import LogTextView
from lutris.util.linux import gather_system_info_str


class SysInfoBox(BaseConfigBox):
    settings_options = {
        "hide_client_on_game_start": _("Minimize client when a game is launched"),
        "hide_text_under_icons": _("Hide text under icons"),
        "show_tray_icon": _("Show Tray Icon"),
    }

    def __init__(self):
        super().__init__()

        self.add(self.get_section_label(_("System information")))

        sysinfo_frame = Gtk.Frame(visible=True)

        scrolled_window = Gtk.ScrolledWindow(visible=True)
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        sysinfo_view = LogTextView(autoscroll=False)
        sysinfo_view.set_cursor_visible(False)
        scrolled_window.add(sysinfo_view)
        sysinfo_frame.add(scrolled_window)
        sysinfo_str = gather_system_info_str()

        text_buffer = sysinfo_view.get_buffer()
        text_buffer.set_text(sysinfo_str)
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self._clipboard_buffer = sysinfo_str

        button_copy = Gtk.Button(_("Copy to clipboard"), visible=True)
        button_copy.connect("clicked", self._copy_text)
        button_copy.set_margin_top(8)
        button_copy.set_halign(Gtk.Align.START)

        self.pack_start(sysinfo_frame, True, True, 0)
        self.add(button_copy)

    def _copy_text(self, widget):  # pylint: disable=unused-argument
        self.clipboard.set_text(self._clipboard_buffer, -1)
