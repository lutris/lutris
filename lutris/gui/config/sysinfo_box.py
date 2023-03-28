from gettext import gettext as _

from gi.repository import Gdk, Gtk

from lutris.gui.widgets.log_text_view import LogTextView
from lutris.util.linux import gather_system_info_str


class SysInfoBox(Gtk.Box):
    settings_options = {
        "hide_client_on_game_start": _("Minimize client when a game is launched"),
        "hide_text_under_icons": _("Hide text under icons"),
        "hide_badges_on_icons": _("Hide badges on icons"),
        "show_tray_icon": _("Show Tray Icon"),
    }

    def __init__(self):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            visible=True,
            spacing=6,
            margin_top=40,
            margin_bottom=40,
            margin_right=100,
            margin_left=100)

        self._clipboard_buffer = None

        sysinfo_frame = Gtk.Frame(visible=True)
        scrolled_window = Gtk.ScrolledWindow(visible=True)
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.sysinfo_view = LogTextView(autoscroll=False, wrap_mode=Gtk.WrapMode.NONE)
        self.sysinfo_view.set_cursor_visible(False)
        scrolled_window.add(self.sysinfo_view)
        sysinfo_frame.add(scrolled_window)

        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        button_copy = Gtk.Button(_("Copy to clipboard"), halign=Gtk.Align.START, visible=True)
        button_copy.connect("clicked", self._copy_text)
        sysinfo_label = Gtk.Label(halign=Gtk.Align.START, visible=True)
        sysinfo_label.set_markup(_("<b>System information</b>"))
        self.pack_start(sysinfo_label, False, False, 0)  # 60, 0)
        self.pack_start(sysinfo_frame, True, True, 0)  # 60, 24)
        self.pack_start(button_copy, False, False, 0)  # 60, 486)

    def populate(self):
        sysinfo_str = gather_system_info_str()

        text_buffer = self.sysinfo_view.get_buffer()
        text_buffer.set_text(sysinfo_str)
        self._clipboard_buffer = sysinfo_str

    def _copy_text(self, widget):  # pylint: disable=unused-argument
        self.clipboard.set_text(self._clipboard_buffer, -1)
