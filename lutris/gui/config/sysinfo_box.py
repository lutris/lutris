from gettext import gettext as _

from gi.repository import Gdk, Gtk

from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.util import linux, system
from lutris.util.linux import gather_system_info_dict
from lutris.util.strings import gtk_safe
from lutris.util.wine.wine import is_esync_limit_set, is_fsync_supported, is_installed_systemwide


class SystemBox(BaseConfigBox):
    features_definitions = [
        {
            "name": _("Vulkan support"),
            "callable": linux.LINUX_SYSTEM.is_vulkan_supported,
        },
        {
            "name": _("Esync support"),
            "callable": is_esync_limit_set,
        },
        {
            "name": _("Fsync support"),
            "callable": is_fsync_supported,
        },
        {
            "name": _("Wine installed"),
            "callable": is_installed_systemwide,
        },
        {
            "name": _("Gamescope"),
            "callable": system.can_find_executable,
            "args": ("gamescope",)
        },
        {
            "name": _("Mangohud"),
            "callable": system.can_find_executable,
            "args": ("mangohud",)
        },
        {
            "name": _("Gamemode"),
            "callable": linux.LINUX_SYSTEM.gamemode_available
        },
        {
            "name": _("Steam"),
            "callable": linux.LINUX_SYSTEM.has_steam
        },
        {
            "name": _("In Flatpak"),
            "callable": linux.LINUX_SYSTEM.is_flatpak
        },
    ]

    def __init__(self):
        super().__init__()
        self.pack_start(self.get_section_label(_("System information")), False, False, 0)

        self.scrolled_window = Gtk.ScrolledWindow(visible=True)
        self.scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sysinfo_frame = Gtk.Frame(visible=True)
        sysinfo_frame.get_style_context().add_class("info-frame")
        sysinfo_frame.add(self.scrolled_window)
        self.pack_start(sysinfo_frame, True, True, 0)

        button_copy = Gtk.Button(_("Copy to Clipboard"), halign=Gtk.Align.START, visible=True)
        button_copy.connect("clicked", self.on_copy_clicked)

        self.pack_start(button_copy, False, False, 0)

    def populate(self):
        items = self.get_items()
        self.scrolled_window.add(self.get_grid(items))

    def get_items(self):
        features = self.get_features()
        items = [(f["name"], f["available_text"]) for f in features]

        system_info_readable = gather_system_info_dict()
        for section, dictionary in system_info_readable.items():
            items.append(section)
            for key, value in dictionary.items():
                items.append((gtk_safe(key), gtk_safe(value)))

        return items

    @staticmethod
    def get_grid(items):
        grid = Gtk.Grid(visible=True, row_spacing=6, margin=16)
        row = 0
        for item in items:
            if isinstance(item, str):
                header_label = Gtk.Label(visible=True, xalign=0, yalign=0, margin_top=16)
                header_label.set_markup("<b>[%s]</b>" % gtk_safe(item))
                if row == 0:
                    grid.set_margin_top(0)
                grid.attach(header_label, 0, row, 2, 1)
            else:
                name, text = item
                name_label = Gtk.Label(name + ":",
                                       visible=True, xalign=0, yalign=0,
                                       margin_right=30)
                grid.attach(name_label, 0, row, 1, 1)

                markup_label = Gtk.Label(visible=True, xalign=0, selectable=True)
                markup_label.set_markup("<b>%s</b>" % gtk_safe(text))
                grid.attach(markup_label, 1, row, 1, 1)
            row += 1
        return grid

    @staticmethod
    def get_text(items):
        lines = []
        for item in items:
            if isinstance(item, str):
                lines.append(f"[{item}]")
            else:
                name, text = item
                lines.append(f"{name}: {text}")
        return "\n".join(lines)

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

    def on_copy_clicked(self, _widget):
        items = self.get_items()
        text = self.get_text(items)

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text.strip(), -1)
