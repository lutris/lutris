from gettext import gettext as _

from gi.repository import Gdk, Gtk

from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.widgets.log_text_view import LogTextView
from lutris.util import linux, system
from lutris.util.linux import gather_system_info_str
from lutris.util.wine.wine import is_esync_limit_set, is_fsync_supported, is_installed_systemwide


class SystemBox(BaseConfigBox):

    def __init__(self):
        super().__init__()

        self._clipboard_buffer = None
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        self.add(self.get_section_label(_("System features")))
        feature_widgets = self.get_feature_widgets()
        self.add(self._get_framed_options_list_box(feature_widgets))

        sysinfo_label = Gtk.Label(halign=Gtk.Align.START, visible=True)
        sysinfo_label.set_markup(_("<b>System information</b>"))
        self.pack_start(sysinfo_label, False, False, 0)

        sysinfo_frame = Gtk.Frame(visible=True)
        scrolled_window = Gtk.ScrolledWindow(visible=True)
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.sysinfo_view = LogTextView(autoscroll=False, wrap_mode=Gtk.WrapMode.NONE)
        self.sysinfo_view.set_cursor_visible(False)
        scrolled_window.add(self.sysinfo_view)
        sysinfo_frame.add(scrolled_window)
        self.pack_start(sysinfo_frame, True, True, 0)

        button_copy = Gtk.Button(_("Copy to Clipboard"), halign=Gtk.Align.START, visible=True)
        button_copy.connect("clicked", self._copy_text)

        self.pack_start(button_copy, False, False, 0)

    def get_feature_widgets(self):
        """Return a list of labels related to this system's features"""
        yes = _("YES")
        no = _("NO")
        labels = []
        features = [
            {
                "label": _("Vulkan support:\t<b>%s</b>"),
                "callable": linux.LINUX_SYSTEM.is_vulkan_supported,
            },
            {
                "label": _("Esync support:\t<b>%s</b>"),
                "callable": is_esync_limit_set,
            },
            {
                "label": _("Fsync support:\t<b>%s</b>"),
                "callable": is_fsync_supported,
            },
            {
                "label": _("Wine installed:\t<b>%s</b>"),
                "callable": is_installed_systemwide,
            },
            {
                "label": _("Gamescope:\t\t<b>%s</b>"),
                "callable": system.can_find_executable,
                "args": ("gamescope", )
            },
            {
                "label": _("Mangohud:\t\t<b>%s</b>"),
                "callable": system.can_find_executable,
                "args": ("mangohud", )
            },
            {
                "label": _("Gamemode:\t\t<b>%s</b>"),
                "callable": linux.LINUX_SYSTEM.gamemode_available
            },
            {
                "label": _("Steam:\t\t\t<b>%s</b>"),
                "callable": linux.LINUX_SYSTEM.has_steam
            },
            {
                "label": _("In Flatpak:\t\t<b>%s</b>"),
                "callable": linux.LINUX_SYSTEM.is_flatpak
            },
        ]
        for feature in features:
            label = Gtk.Label(visible=True, xalign=0)
            label.set_margin_top(3)
            label.set_margin_bottom(3)
            label.set_margin_start(16)
            label.set_markup(feature["label"] % (yes if feature["callable"](*feature.get("args", ())) else no))
            labels.append(label)
        return labels

    def populate(self):
        sysinfo_str = gather_system_info_str()

        text_buffer = self.sysinfo_view.get_buffer()
        text_buffer.set_text(sysinfo_str)
        self._clipboard_buffer = sysinfo_str

    def _copy_text(self, _widget):
        self.clipboard.set_text(self._clipboard_buffer, -1)
