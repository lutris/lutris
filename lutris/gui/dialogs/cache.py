from gettext import gettext as _

from gi.repository import Gtk

from lutris.cache import (
    delete_installer_cache_entry,
    get_custom_cache_path,
    get_installer_cache_entries,
    save_custom_cache_path,
)
from lutris.gui.dialogs import ModalDialog, QuestionDialog
from lutris.gui.widgets.common import FileChooserEntry
from lutris.util.strings import gtk_safe, human_size


class CacheConfigurationDialog(ModalDialog):
    def __init__(self, parent=None):
        super().__init__(
            _("Download cache configuration"), parent=parent, flags=Gtk.DialogFlags.MODAL, border_width=10
        )
        self.timer_id = None
        self.set_size_request(640, 380)

        self.cache_path = get_custom_cache_path() or ""
        self.cache_entries_store = Gtk.ListStore(str, str, str)
        self.cache_entries_view = None
        self.get_content_area().add(self.get_cache_config())

        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)

        self.show_all()
        result = self.run()

        if result == Gtk.ResponseType.OK:
            save_custom_cache_path(self.cache_path)

        self.destroy()

    def get_cache_config(self):
        """Return the widgets for the cache configuration"""
        prefs_box = Gtk.VBox(spacing=12)

        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Gtk.Label(_("Cache path"))
        box.pack_start(label, False, False, 0)
        path_chooser = FileChooserEntry(
            title=_("Set the folder for the cache path"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            warn_if_non_writable_parent=True,
            text=self.cache_path,
            activates_default=True,
        )
        path_chooser.connect("changed", self._on_cache_path_set)
        box.pack_start(path_chooser, True, True, 0)

        prefs_box.pack_start(box, False, False, 6)
        cache_help_label = Gtk.Label(visible=True)
        cache_help_label.set_size_request(400, -1)
        cache_help_label.set_markup(
            _(
                "If provided, this location will be used by installers to cache "
                "downloaded files locally for future re-use. \nIf left empty, the "
                "installer files are discarded after the install completion."
            )
        )
        prefs_box.pack_start(cache_help_label, False, False, 6)
        prefs_box.pack_start(self.get_cache_entries_box(), True, True, 6)
        return prefs_box

    def get_cache_entries_box(self):
        box = Gtk.VBox(spacing=6)
        box.set_margin_left(12)
        box.set_margin_right(12)

        heading = Gtk.Label(label=_("Cached installers"))
        heading.set_alignment(0, 0)
        box.pack_start(heading, False, False, 0)

        self.cache_entries_view = Gtk.TreeView(model=self.cache_entries_store)
        self.cache_entries_view.set_headers_visible(True)
        self.cache_entries_view.get_selection().set_mode(Gtk.SelectionMode.SINGLE)

        name_renderer = Gtk.CellRendererText()
        name_column = Gtk.TreeViewColumn(_("Game"), name_renderer, text=0)
        name_column.set_expand(True)
        self.cache_entries_view.append_column(name_column)

        size_renderer = Gtk.CellRendererText()
        self.cache_entries_view.append_column(Gtk.TreeViewColumn(_("Size"), size_renderer, text=1))

        path_renderer = Gtk.CellRendererText()
        path_column = Gtk.TreeViewColumn(_("Location"), path_renderer, text=2)
        path_column.set_expand(True)
        self.cache_entries_view.append_column(path_column)

        scrolled = Gtk.ScrolledWindow(hexpand=True, vexpand=True, child=self.cache_entries_view)
        scrolled.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        box.pack_start(scrolled, True, True, 0)

        delete_button = Gtk.Button(label=_("Delete selected cached installer"))
        delete_button.connect("clicked", self._on_delete_cache_entry_clicked)
        box.pack_start(delete_button, False, False, 0)

        self.refresh_cache_entries()
        return box

    def refresh_cache_entries(self):
        self.cache_entries_store.clear()
        for entry in get_installer_cache_entries():
            self.cache_entries_store.append([entry["name"], human_size(entry["size"]), entry["path"]])

    def _on_delete_cache_entry_clicked(self, _button):
        if not self.cache_entries_view:
            return

        model, tree_iter = self.cache_entries_view.get_selection().get_selected()
        if tree_iter is None:
            return

        path = model[tree_iter][2]
        dlg = QuestionDialog(
            {
                "parent": self,
                "title": _("Delete cached installer?"),
                "question": _("Delete the cached installer files in %s?") % gtk_safe(path),
            }
        )
        if dlg.result != Gtk.ResponseType.YES:
            return

        delete_installer_cache_entry(path)
        self.refresh_cache_entries()

    def _on_cache_path_set(self, entry):
        self.cache_path = entry.get_text()
