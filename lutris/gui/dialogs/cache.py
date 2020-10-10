from gettext import gettext as _

from gi.repository import GLib, Gtk

from lutris.cache import get_cache_path, save_cache_path
from lutris.gui.widgets.common import FileChooserEntry


class CacheConfigurationDialog(Gtk.Dialog):
    def __init__(self):
        Gtk.Dialog.__init__(self, _("Cache configuration"))
        self.timer_id = None
        self.set_size_request(480, 150)
        self.set_border_width(12)

        self.get_content_area().add(self.get_cache_config())
        self.show_all()

    def get_cache_config(self):
        """Return the widgets for the cache configuration"""
        prefs_box = Gtk.VBox()

        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Gtk.Label(_("Cache path"))
        box.pack_start(label, False, False, 0)
        cache_path = get_cache_path()
        path_chooser = FileChooserEntry(
            title=_("Set the folder for the cache path"), action=Gtk.FileChooserAction.SELECT_FOLDER, path=cache_path
        )
        path_chooser.entry.connect("changed", self._on_cache_path_set)
        box.pack_start(path_chooser, True, True, 0)

        prefs_box.pack_start(box, False, False, 6)
        cache_help_label = Gtk.Label(visible=True)
        cache_help_label.set_size_request(400, -1)
        cache_help_label.set_markup(_(
            "If provided, this location will be used by installers to cache "
            "downloaded files locally for future re-use. \nIf left empty, the "
            "installer files are discarded after the install completion."
        ))
        prefs_box.pack_start(cache_help_label, False, False, 6)
        return prefs_box

    def _on_cache_path_set(self, entry):
        if self.timer_id:
            GLib.source_remove(self.timer_id)
        self.timer_id = GLib.timeout_add(1000, self.save_cache_setting, entry.get_text())

    def save_cache_setting(self, value):
        save_cache_path(value)
        GLib.source_remove(self.timer_id)
        self.timer_id = None
        return False
