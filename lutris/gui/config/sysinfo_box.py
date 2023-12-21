from gettext import gettext as _

from gi.repository import Gdk, Gtk

from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.widgets.log_text_view import LogTextView
from lutris.util import linux, system
from lutris.util.linux import gather_system_info_str
from lutris.util.wine.wine import is_esync_limit_set, is_fsync_supported, is_installed_systemwide


class SystemBox(BaseConfigBox):
    features_definitions = [
        {
            "name": _("Vulkan support"),
            "label_markup": _("Vulkan support:\t<b>%s</b>"),
            "callable": linux.LINUX_SYSTEM.is_vulkan_supported,
        },
        {
            "name": _("Esync support"),
            "label_markup": _("Esync support:\t<b>%s</b>"),
            "callable": is_esync_limit_set,
        },
        {
            "name": _("Fsync support"),
            "label_markup": _("Fsync support:\t<b>%s</b>"),
            "callable": is_fsync_supported,
        },
        {
            "name": _("Wine installed"),
            "label_markup": _("Wine installed:\t<b>%s</b>"),
            "callable": is_installed_systemwide,
        },
        {
            "name": _("Gamescope"),
            "label_markup": _("Gamescope:\t\t<b>%s</b>"),
            "callable": system.can_find_executable,
            "args": ("gamescope",)
        },
        {
            "name": _("Mangohud"),
            "label_markup": _("Mangohud:\t\t<b>%s</b>"),
            "callable": system.can_find_executable,
            "args": ("mangohud",)
        },
        {
            "name": _("Gamemode"),
            "label_markup": _("Gamemode:\t\t<b>%s</b>"),
            "callable": linux.LINUX_SYSTEM.gamemode_available
        },
        {
            "name": _("Steam"),
            "label_markup": _("Steam:\t\t\t<b>%s</b>"),
            "callable": linux.LINUX_SYSTEM.has_steam
        },
        {
            "name": _("In Flatpak"),
            "label_markup": _("In Flatpak:\t\t<b>%s</b>"),
            "callable": linux.LINUX_SYSTEM.is_flatpak
        },
    ]

    def __init__(self):
        super().__init__()

        self.add(self.get_section_label(_("System features")))
        features_grid = self.get_features_grid()
        self.add(self._get_framed_options_list_box([features_grid]))

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

    def get_features_grid(self):
        """Return a list of labels related to this system's features"""
        grid = Gtk.Grid(visible=True, row_spacing=6, margin=16)
        row = 0
        features = self.get_features()
        for feature in features:
            label = Gtk.Label(feature["name"] + ":",
                              visible=True, xalign=0, yalign=0,
                              margin_right=30)
            grid.attach(label, 0, row, 1, 1)

            status = Gtk.Label(visible=True, xalign=0)
            status.set_markup("<b>%s</b>" % feature["available_text"])
            grid.attach(status, 1, row, 1, 1)
            row += 1
        return grid

    def get_features(self):
        yes = _("YES")
        no = _("NO")

        def eval_feature(feature):
            result = feature.copy()
            func = feature["callable"]
            args = feature.get("args", ())
            result["availability"] = bool(func(*args))
            result["available_text"] = yes if result["availability"] else no
            return result

        return [eval_feature(f) for f in self.features_definitions]

    def populate(self):
        text_buffer = self.sysinfo_view.get_buffer()
        text_buffer.set_text(gather_system_info_str())

    def _copy_text(self, _widget):
        features = self.get_features()
        _clipboard_buffer = "[Features]\n"

        for f in features:
            _clipboard_buffer += "%s: %s\n" % (f["name"], f["available_text"])

        _clipboard_buffer += "\n"
        _clipboard_buffer += gather_system_info_str()
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(_clipboard_buffer.strip(), -1)
