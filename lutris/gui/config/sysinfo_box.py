from gettext import gettext as _

from gi.repository import Gdk, Gtk

from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.util import linux, system
from lutris.util.linux import gather_system_info_dict, gather_system_info_str
from lutris.util.strings import gtk_safe
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
        self.features_frame = Gtk.Frame(visible=True)
        self.features_frame.get_style_context().add_class("info-frame")
        self.pack_start(self.features_frame, False, False, 0)

        self.pack_start(self.get_section_label(_("System information")), False, False, 0)

        self.scrolled_window = Gtk.ScrolledWindow(visible=True)
        self.scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sysinfo_frame = Gtk.Frame(visible=True)
        sysinfo_frame.get_style_context().add_class("info-frame")
        sysinfo_frame.add(self.scrolled_window)
        self.pack_start(sysinfo_frame, True, True, 0)

        button_copy = Gtk.Button(_("Copy to Clipboard"), halign=Gtk.Align.START, visible=True)
        button_copy.connect("clicked", self._copy_text)

        self.pack_start(button_copy, False, False, 0)

    def populate(self):
        features_grid = self.get_features_grid()
        self.features_frame.add(features_grid)

        sysinfo_grid = self.get_system_info_grid()
        self.scrolled_window.add(sysinfo_grid)

    def get_features_grid(self):
        features = self.get_features()
        items = ((f["name"], f["available_text"]) for f in features)
        return self.get_grid(items)

    def get_system_info_grid(self):
        system_info_readable = gather_system_info_dict()
        items = []
        for section, dictionary in system_info_readable.items():
            items.append("<b>[%s]</b>" % section)
            for key, value in dictionary.items():
                items.append((gtk_safe(key), gtk_safe(value)))
        return self.get_grid(items)

    @staticmethod
    def get_grid(items):
        grid = Gtk.Grid(visible=True, row_spacing=6, margin=16)
        row = 0
        for item in items:
            if isinstance(item, str):
                header_label = Gtk.Label(visible=True, xalign=0, yalign=0, margin_top=16)
                header_label.set_markup(str(item))
                grid.set_margin_top(0)
                grid.attach(header_label, 0, row, 2, 1)
            else:
                name, markup = item
                name_label = Gtk.Label(name + ":",
                                       visible=True, xalign=0, yalign=0,
                                       margin_right=30)
                grid.attach(name_label, 0, row, 1, 1)

                markup_label = Gtk.Label(visible=True, xalign=0, selectable=True)
                markup_label.set_markup("<b>%s</b>" % markup)
                grid.attach(markup_label, 1, row, 1, 1)
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

    def _copy_text(self, _widget):
        features = self.get_features()
        _clipboard_buffer = "[Features]\n"

        for f in features:
            _clipboard_buffer += "%s: %s\n" % (f["name"], f["available_text"])

        _clipboard_buffer += "\n"
        _clipboard_buffer += gather_system_info_str()
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(_clipboard_buffer.strip(), -1)
