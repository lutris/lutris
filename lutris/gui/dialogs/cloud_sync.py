"""Cloud sync dialogs for GOG cloud save integration.

Provides dialogs for conflict resolution and sync status notifications
during game launch and quit.
"""

from gettext import gettext as _

from gi.repository import Gtk

from lutris.gui.dialogs import ModalDialog


class CloudSyncConflictDialog(ModalDialog):
    """Dialog shown when local and cloud saves are in conflict.

    Presents the user with three options:
    - Use Cloud Saves (download)
    - Use Local Saves (upload)
    - Skip Sync (do nothing)

    After construction the result is available as ``self.action``:
    - ``"download"`` — overwrite local with cloud saves
    - ``"upload"`` — overwrite cloud with local saves
    - ``None`` — skip sync
    """

    def __init__(self, game_name: str, location_name: str, parent=None):
        super().__init__(title=_("Cloud Save Conflict"), parent=parent)
        self.action = None
        self.set_border_width(12)
        self.set_default_size(420, -1)

        content = self.get_content_area()

        # Header
        header = Gtk.Label(visible=True)
        header.set_markup(_("<b>Cloud save conflict for <i>%s</i></b>") % game_name)
        header.set_line_wrap(True)
        content.pack_start(header, False, False, 6)

        # Description
        desc = Gtk.Label(visible=True)
        desc.set_markup(
            _(
                "Both local and cloud saves for <b>%s</b> have been modified "
                "since the last sync.\n\n"
                "Choose which version to keep:"
            )
            % location_name
        )
        desc.set_line_wrap(True)
        content.pack_start(desc, False, False, 12)

        # Buttons
        self.add_button(_("Skip Sync"), Gtk.ResponseType.CANCEL)
        upload_btn = self.add_button(_("Use Local Saves"), Gtk.ResponseType.NO)
        download_btn = self.add_button(_("Use Cloud Saves"), Gtk.ResponseType.YES)
        download_btn.get_style_context().add_class("suggested-action")

        # Tooltips
        upload_btn.set_tooltip_text(_("Upload your local saves to the cloud, overwriting the cloud version"))
        download_btn.set_tooltip_text(_("Download cloud saves to your computer, overwriting the local version"))

        response = self.run()
        self.destroy()

        if response == Gtk.ResponseType.YES:
            self.action = "download"
        elif response == Gtk.ResponseType.NO:
            self.action = "upload"
        # else: None (skip)
