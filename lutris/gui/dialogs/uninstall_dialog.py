# pylint: disable=no-member
import os
from gettext import gettext as _
from typing import Callable, Iterable, List

from gi.repository import GObject, Gtk

from lutris import settings
from lutris.database.games import get_game_by_field, get_games
from lutris.game import Game
from lutris.gui.dialogs import QuestionDialog
from lutris.gui.widgets.gi_composites import GtkTemplate
from lutris.gui.widgets.utils import get_required_main_window, get_widget_children
from lutris.util import datapath
from lutris.util.jobs import AsyncCall
from lutris.util.library_sync import LibrarySyncer
from lutris.util.log import logger
from lutris.util.path_cache import remove_from_path_cache
from lutris.util.strings import get_natural_sort_key, gtk_safe, human_size
from lutris.util.system import get_disk_size, is_removeable


@GtkTemplate(ui=os.path.join(datapath.get(), "ui", "uninstall-dialog.ui"))
class UninstallDialog(Gtk.Dialog):
    """A dialog to uninstall and remove games. It lists the games and offers checkboxes to delete
    the game files, and to remove from the library."""

    __gtype_name__ = "UninstallDialog"

    header_bar: Gtk.HeaderBar = GtkTemplate.Child()
    message_label: Gtk.Label = GtkTemplate.Child()
    uninstall_game_list: Gtk.ListBox = GtkTemplate.Child()
    cancel_button: Gtk.Button = GtkTemplate.Child()
    uninstall_button: Gtk.Button = GtkTemplate.Child()
    delete_all_files_checkbox: Gtk.CheckButton = GtkTemplate.Child()
    remove_all_games_checkbox: Gtk.CheckButton = GtkTemplate.Child()

    def __init__(self, parent: Gtk.Window, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.parent = parent
        self._setting_all_checkboxes = False
        self.games: List[Game] = []
        self.any_shared = False
        self.any_protected = False
        self.init_template()
        self.show_all()

    def get_game_removal_rows(self) -> List["GameRemovalRow"]:
        return get_widget_children(self.uninstall_game_list, GameRemovalRow)

    def add_games(self, game_ids: Iterable[str]) -> None:
        new_game_ids = set(game_ids) - set(g.id for g in self.games)
        new_games = [Game(game_id) for game_id in new_game_ids]
        new_games.sort(key=lambda g: get_natural_sort_key(g.name))
        self.games += new_games

        new_rows = []
        for game in new_games:
            row = GameRemovalRow(game)
            self.uninstall_game_list.add(row)
            new_rows.append(row)

        self.update_deletability()
        self.update_folder_sizes(new_games)
        self.update_subtitle()
        self.update_message()
        self.update_all_checkboxes()
        self.update_uninstall_button()
        self.uninstall_game_list.show_all()

        # Defer the connection until all checkboxes are updated
        for row in new_rows:
            row.connect("row-updated", self.on_row_updated)

    def update_deletability(self) -> None:
        """Updates the can_delete_files property on each row; adding new rows can set this on existing rows
        (they might no longer violate the 'can't delete shared directory' rule). This also sets flags that
        are used by later update methods, so this must be called first."""
        self.any_shared = False
        self.any_protected = False

        def is_shared(directory: str) -> bool:
            dir_users = set(str(g["id"]) for g in get_games(filters={"directory": directory, "installed": 1}))
            for g in self.games:
                dir_users.discard(g.id)
            return bool(dir_users)

        for row in self.get_game_removal_rows():
            game = row.game
            if game.is_installed and game.directory:
                if game.config and is_removeable(game.directory, game.config.system_config):
                    shared_dir = is_shared(game.directory)
                    self.any_shared = self.any_shared or shared_dir
                    row.can_delete_files = not shared_dir
                else:
                    row.can_delete_files = False
                    self.any_protected = True
            else:
                row.can_delete_files = False

    def update_folder_sizes(self, new_games: List[Game]) -> None:
        """Starts fetching folder sizes for new games added to the dialog; we only
        do this for the games given in 'new_games', however."""
        folders_to_size = []
        folders_seen = set()

        for row in self.get_game_removal_rows():
            game = row.game
            if game in new_games and game.is_installed and game.directory:
                if game.directory not in folders_seen:
                    folders_seen.add(game.directory)
                    folders_to_size.append(game.directory)
                row.show_folder_size_spinner()

        if folders_to_size:
            AsyncCall(
                self._get_next_folder_size,
                self._get_next_folder_size_cb,
                folders_to_size,
            )

    def update_subtitle(self) -> None:
        """Updates the dialog subtitle according to what games are being removed."""
        to_uninstall = [g for g in self.games if g.is_installed]
        to_remove = [g for g in self.games if not g.is_installed]

        if len(to_uninstall) == 1 and not to_remove:
            subtitle = _("Uninstall %s") % gtk_safe(to_uninstall[0].name)
        elif len(to_remove) == 1 and not to_uninstall:
            subtitle = _("Remove %s") % gtk_safe(to_remove[0].name)
        elif not to_remove:
            subtitle = _("Uninstall %d games") % len(to_uninstall)
        elif not to_uninstall:
            subtitle = _("Remove %d games") % len(to_remove)
        else:
            subtitle = _("Uninstall %d games and remove %d games") % (
                len(to_uninstall),
                len(to_remove),
            )

        self.header_bar.set_subtitle(subtitle)

    def update_message(self) -> None:
        """Updates the message label at the top of the dialog."""
        to_uninstall = [g for g in self.games if g.is_installed]
        messages = []

        if to_uninstall:
            messages.append(_("After you uninstall these games, you won't be able play them in Lutris."))
            messages.append(
                _(
                    "Uninstalled games that you remove from the library will no longer appear in the "
                    "'Games' view, but those that remain will retain their playtime data."
                )
            )
        else:
            messages.append(_("After you remove these games, they will no longer appear in the 'Games' view."))

        if self.any_shared:
            messages.append(
                _(
                    "Some of the game directories cannot be removed because they are shared "
                    "with other games that you are not removing."
                )
            )

        if self.any_protected:
            messages.append(_("Some of the game directories cannot be removed because they are protected."))

        if messages:
            self.message_label.set_markup("\n\n".join(messages))
            self.message_label.show()
        else:
            self.message_label.hide()

    def on_row_updated(self, row) -> None:
        directory = row.game.directory
        if directory and row.can_delete_files:
            for r in self.get_game_removal_rows():
                if row != r and r.game.directory == directory and r.can_delete_files:
                    r.delete_files = row.delete_files

        self.update_all_checkboxes()

    def update_all_checkboxes(self) -> None:
        """Sets the state of the checkboxes at the button that are used to control all
        settings together. While we are actually updating these checkboxes en-mass,
        this method does nothing at all."""

        def update(checkbox, is_candidate, is_set):
            set_count = 0
            unset_count = 0
            for row in self.get_game_removal_rows():
                if is_candidate(row):
                    if is_set(row):
                        set_count += 1
                    else:
                        unset_count += 1

            checkbox.set_active(set_count > 0)
            checkbox.set_inconsistent(set_count > 0 and unset_count > 0)
            checkbox.set_visible((set_count + unset_count) > 1 and (set_count > 0 or unset_count > 0))

        if not self._setting_all_checkboxes:
            self._setting_all_checkboxes = True
            try:
                update(
                    self.delete_all_files_checkbox,
                    lambda row: row.can_delete_files,
                    lambda row: row.delete_files,
                )

                update(
                    self.remove_all_games_checkbox,
                    lambda row: True,
                    lambda row: row.remove_from_library,
                )
            finally:
                self._setting_all_checkboxes = False

    def update_uninstall_button(self) -> None:
        if any(g for g in self.games if g.is_installed):
            self.uninstall_button.set_label(_("Uninstall"))

    @GtkTemplate.Callback
    def on_delete_all_files_checkbox_toggled(self, _widget):
        def update_row(row, active):
            if row.can_delete_files:
                row.delete_files = active

        self._apply_all_checkbox(self.delete_all_files_checkbox, update_row)

    @GtkTemplate.Callback
    def on_remove_all_games_checkbox_toggled(self, _widget):
        def update_row(row, active):
            row.remove_from_library = active

        self._apply_all_checkbox(self.remove_all_games_checkbox, update_row)

    def _apply_all_checkbox(self, checkbox, row_updater: Callable[["GameRemovalRow", bool], None]):
        """Sets the state of the checkboxes on all rows to agree with 'checkbox';
        the actual change is performed by row_updater, so this can be used for
        either checkbox."""
        if not self._setting_all_checkboxes and checkbox.get_visible():
            active = checkbox.get_active()
            self._setting_all_checkboxes = True

            for row in self.get_game_removal_rows():
                row_updater(row, active)

            self._setting_all_checkboxes = False
            self.update_all_checkboxes()

    @GtkTemplate.Callback
    def on_cancel_button_clicked(self, _widget) -> None:
        self.destroy()

    @GtkTemplate.Callback
    def on_remove_button_clicked(self, _widget) -> None:
        rows = list(self.get_game_removal_rows())
        dirs_to_delete = list(set(row.game.directory for row in rows if row.delete_files))

        if dirs_to_delete:
            if len(dirs_to_delete) == 1:
                question = _("Please confirm.\nEverything under <b>%s</b>\nwill be moved to the trash.") % gtk_safe(
                    dirs_to_delete[0]
                )
            else:
                question = _("Please confirm.\nAll the files for %d games will be moved to the trash.") % len(
                    dirs_to_delete
                )

            dlg = QuestionDialog(
                {
                    "parent": self,
                    "question": question,
                    "title": _("Permanently delete files?"),
                }
            )

            if dlg.result != Gtk.ResponseType.YES:
                return

        library_sync_enabled = settings.read_bool_setting("library_sync_enabled", True)
        games_removed_from_library = []
        library_syncer = LibrarySyncer() if library_sync_enabled else None

        for row in rows:
            if library_syncer and row.remove_from_library:
                games_removed_from_library.append(get_game_by_field(row.game._id, "id"))
            row.perform_removal()

        if library_syncer and games_removed_from_library:

            def sync_local_library():
                library_syncer.sync_local_library()
                library_syncer.delete_from_remote_library(games_removed_from_library)

            AsyncCall(sync_local_library, None)

        get_required_main_window().on_game_removed()
        self.destroy()

    def on_response(self, _dialog, response: Gtk.ResponseType) -> None:
        if response in (
            Gtk.ResponseType.DELETE_EVENT,
            Gtk.ResponseType.CANCEL,
            Gtk.ResponseType.OK,
        ):
            self.destroy()

    @staticmethod
    def _get_next_folder_size(directories):
        """This runs on a thread and computes the size of the first directory in
        directories; the _get_next_folder_size_cb will run this again if required,
        until all directories have been sized."""
        directory = directories.pop(0)
        size = get_disk_size(directory)
        return directory, size, directories

    def _get_next_folder_size_cb(self, result, error):
        if error:
            logger.error(error)
            return

        directory, size, remaining_directories = result

        if remaining_directories:
            AsyncCall(
                self._get_next_folder_size,
                self._get_next_folder_size_cb,
                remaining_directories,
            )

        for row in self.get_game_removal_rows():
            if directory == row.game.directory:
                row.show_folder_size(size)


class GameRemovalRow(Gtk.ListBoxRow):
    __gsignals__ = {
        "row-updated": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, game: Game):
        super().__init__(activatable=False)
        self.game = game
        self._can_delete_files = False
        self.delete_files_checkbox: Gtk.CheckButton = None
        self.folder_size_spinner: Gtk.Spinner = None
        self.directory_label: Gtk.Label = None

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.pack_start(hbox, False, False, 0)

        label = Gtk.Label(label=game.name, selectable=True)
        hbox.pack_start(label, False, False, 0)

        self.remove_from_library_checkbox = Gtk.CheckButton(label=_("Remove from Library"), halign=Gtk.Align.START)
        self.remove_from_library_checkbox.set_active(False)
        self.remove_from_library_checkbox.connect("toggled", self.on_checkbox_toggled)
        hbox.pack_end(self.remove_from_library_checkbox, False, False, 0)

        if game.is_installed and self.game.directory:
            self.delete_files_checkbox = Gtk.CheckButton(label=_("Delete Files"))
            self.delete_files_checkbox.set_sensitive(False)
            self.delete_files_checkbox.set_active(False)
            self.delete_files_checkbox.set_tooltip_text(self.game.directory)
            self.delete_files_checkbox.connect("toggled", self.on_checkbox_toggled)

            hbox.pack_end(self.delete_files_checkbox, False, False, 0)

            dir_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=6,
                margin_left=6,
                margin_right=6,
                height_request=16,
            )
            self.directory_label = Gtk.Label(halign=Gtk.Align.START, selectable=True, valign=Gtk.Align.START)
            self.directory_label.set_markup(self._get_directory_markup())
            dir_box.pack_start(self.directory_label, False, False, 0)

            self.folder_size_spinner = Gtk.Spinner(visible=False, no_show_all=True)
            dir_box.pack_start(self.folder_size_spinner, False, False, 0)

            vbox.pack_start(dir_box, False, False, 0)
        self.add(vbox)

    def _get_directory_markup(self, folder_size: int = None):
        if not self.game.directory or not self.game.is_installed:
            return ""

        markup = gtk_safe(self.game.directory)
        if folder_size is not None:
            markup += f" <i>({human_size(folder_size)})</i>"
        return "<span font_desc='8'>%s</span>" % markup

    def on_checkbox_toggled(self, _widget):
        self.emit("row-updated")

    def show_folder_size_spinner(self):
        if self.folder_size_spinner:
            self.folder_size_spinner.start()
            self.folder_size_spinner.show()

    def show_folder_size(self, folder_size: int) -> None:
        """Called to stop the spinner and show the size of the game folder."""
        if self.directory_label:
            self.directory_label.set_markup(self._get_directory_markup(folder_size))

        if self.folder_size_spinner:
            self.folder_size_spinner.stop()
            self.folder_size_spinner.hide()

    @property
    def delete_files(self) -> bool:
        """True if the game files should be deleted."""
        return bool(
            self.game.is_installed
            and self.game.directory
            and self.delete_files_checkbox
            and self.delete_files_checkbox.get_active()
        )

    @delete_files.setter
    def delete_files(self, active: bool) -> None:
        self.delete_files_checkbox.set_active(active)

    @property
    def can_delete_files(self):
        return self._can_delete_files

    @can_delete_files.setter
    def can_delete_files(self, can_delete):
        if self._can_delete_files != can_delete and self.delete_files_checkbox:
            self._can_delete_files = can_delete
            self.delete_files_checkbox.set_sensitive(can_delete)
            self.delete_files_checkbox.set_active(can_delete)

    @property
    def remove_from_library(self) -> bool:
        """True if the game should be removed from the database."""
        return bool(self.remove_from_library_checkbox.get_active())

    @remove_from_library.setter
    def remove_from_library(self, active: bool) -> None:
        self.remove_from_library_checkbox.set_active(active)

    def perform_removal(self) -> None:
        """Performs the actions this row describes, uninstalling or deleting a game."""
        # We uninstall installed games, and delete games where self.remove_from_library is true
        if self.game.is_installed:
            remove_from_path_cache(self.game)
            if self.remove_from_library:
                self.game.uninstall(delete_files=self.delete_files)
                self.game.delete()
            else:
                self.game.uninstall(delete_files=self.delete_files)
        elif self.remove_from_library:
            self.game.delete()
