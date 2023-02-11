from gettext import gettext as _

from gi.repository import Gtk

from lutris.cache import get_cache_path, save_cache_path
from lutris.gui.dialogs import ModalDialog
from lutris.gui.widgets.common import FileChooserEntry


class CacheConfigurationDialog(ModalDialog):
    def __init__(self, parent=None):
        super().__init__(
            _("Download cache configuration"),
            parent=parent,
            flags=Gtk.DialogFlags.MODAL,
            border_width=10
        )
        self.timer_id = None
        self.set_size_request(480, 150)

        self.cache_path = get_cache_path() or ""
        self.get_content_area().add(self.get_cache_config())

        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)

        self.show_all()
        result = self.run()

        if result == Gtk.ResponseType.OK:
            save_cache_path(self.cache_path)

        self.destroy()

    def get_cache_config(self):
        """Return the widgets for the cache configuration"""
        prefs_box = Gtk.VBox()

        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Gtk.Label(_("Cache path"))
        box.pack_start(label, False, False, 0)
        path_chooser = FileChooserEntry(
            title=_("Set the folder for the cache path"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            path=self.cache_path,
            activates_default=True
        )
        path_chooser.connect("changed", self._on_cache_path_set)
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
        self.cache_path = entry.get_text()
