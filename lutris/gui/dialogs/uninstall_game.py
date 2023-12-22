# pylint: disable=no-member
import os
from gettext import gettext as _
from typing import Callable, Dict, List

from gi.repository import Gtk

from lutris.database.games import get_games
from lutris.game import Game
from lutris.gui.dialogs import QuestionDialog
from lutris.gui.widgets.gi_composites import GtkTemplate
from lutris.util import datapath
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import gtk_safe, human_size
from lutris.util.system import get_disk_size, is_removeable


@GtkTemplate(ui=os.path.join(datapath.get(), "ui", "uninstall-dialog.ui"))
class UninstallMultipleGamesDialog(Gtk.Dialog):
    """A dialog to uninstall and remove games. It lists the games and offers checkboxes to delete
    the game files, and to remove from the library."""
    __gtype_name__ = "UninstallMultipleGamesDialog"

    header_bar: Gtk.HeaderBar = GtkTemplate.Child()
    message_label: Gtk.Label = GtkTemplate.Child()
    uninstall_game_list: Gtk.ListBox = GtkTemplate.Child()
    cancel_button: Gtk.Button = GtkTemplate.Child()
    uninstall_button: Gtk.Button = GtkTemplate.Child()
    delete_all_files_checkbox: Gtk.CheckButton = GtkTemplate.Child()
    remove_all_games_checkbox: Gtk.CheckButton = GtkTemplate.Child()

    def __init__(self, game_ids: List[str], parent: Gtk.Window = None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.games = [Game(game_id) for game_id in game_ids]
        self._setting_all_checkboxes = False

        to_uninstall = [g for g in self.games if g.is_installed]
        to_remove = [g for g in self.games if not g.is_installed]
        any_shared = False
        any_protected = False

        def get_messages() -> List[str]:
            msgs = []

            if to_uninstall:
                msgs.append(_("After you uninstall these games, you won't be able play them in Lutris."))
                msgs.append(_("Uninstalled games that you remove from the library will no longer appear in the "
                              "'Games' view, but those that remain will retain their playtime data."))
            else:
                msgs.append(_("After you remove these games, they will no longer "
                              "appear in the 'Games' view."))

            if any_shared:
                msgs.append(_("Some of the game directories cannot be removed because they are shared "
                              "with other games that you are not removing."))

            if any_protected:
                msgs.append(_("Some of the game directories cannot be removed because they are protected."))

            return msgs

        def get_subtitle() -> str:
            if len(to_uninstall) == 1 and not to_remove:
                return _("Uninstall %s") % gtk_safe(to_uninstall[0].name)
            if len(to_remove) == 1 and not to_uninstall:
                return _("Remove %s") % gtk_safe(to_remove[0].name)
            if not to_remove:
                return _("Uninstall %d games") % len(to_uninstall)
            if not to_uninstall:
                return _("Remove %d games") % len(to_remove)

            return _("Uninstall %d games and remove %d games") % (
                len(to_uninstall), len(to_remove))

        def is_shared(directory: str) -> bool:
            dir_users = set(str(g["id"]) for g in get_games(filters={"directory": directory, "installed": 1}))
            for g in self.games:
                dir_users.discard(g.id)
            return bool(dir_users)

        self.init_template()

        if not any(g for g in self.games if g.is_installed):
            self.uninstall_button.set_label(_("Remove"))

        folders_to_size = []

        for game in self.games:
            if game.is_installed and game.directory:
                if game.config and is_removeable(game.directory, game.config.system_config):
                    shared_dir = is_shared(game.directory)
                    any_shared = any_shared or shared_dir
                    can_delete_files = not shared_dir
                else:
                    can_delete_files = False
                    any_protected = True
            else:
                can_delete_files = False

            row = UninstallMultipleGamesDialog.GameRemovalRow(game, can_delete_files, self.update_all_checkboxes)

            if can_delete_files and row.can_show_folder_size:
                folders_to_size.append(game.directory)

            self.uninstall_game_list.add(row)

        if folders_to_size:
            AsyncCall(self._get_disk_size, self._folder_size_cb, folders_to_size)

        self.header_bar.set_subtitle(get_subtitle())

        messages = get_messages()
        if messages:
            self.message_label.set_markup("\n\n".join(messages))
            self.message_label.show()
        else:
            self.message_label.hide()

        self.update_all_checkboxes()
        self.show_all()

    def update_all_checkboxes(self) -> None:
        """Sets the state of the checkboxes at the button that are used to control all
        settings together. While we are actually updating these checkboxes en-meass,
        this method does nothing at all."""

        def update(checkbox, is_candidate, is_set):
            set_count = 0
            unset_count = 0
            for row in self.uninstall_game_list.get_children():
                if is_candidate(row):
                    if is_set(row):
                        set_count += 1
                    else:
                        unset_count += 1

            checkbox.set_active(set_count > 0)
            checkbox.set_inconsistent(set_count > 0 and unset_count > 0)
            checkbox.set_visible((set_count + unset_count) > 1 and (set_count > 0 or unset_count > 0))

        if not self._setting_all_checkboxes:
            update(self.delete_all_files_checkbox,
                   lambda row: row.can_delete_files,
                   lambda row: row.delete_files)

            update(self.remove_all_games_checkbox,
                   lambda row: row.game.is_installed,
                   lambda row: row.delete_game)

    @GtkTemplate.Callback
    def on_delete_all_files_checkbox_toggled(self, _widget):
        def update_row(row, active):
            if row.can_delete_files:
                row.delete_files = active

        self._apply_all_checkbox(self.delete_all_files_checkbox, update_row)

    @GtkTemplate.Callback
    def on_remove_all_games_checkbox_toggled(self, _widget):
        def update_row(row, active):
            if row.game.is_installed:
                row.delete_game = active

        self._apply_all_checkbox(self.remove_all_games_checkbox, update_row)

    def _apply_all_checkbox(self, checkbox,
                            row_updater: Callable[['GameRemovalRow', bool], None]):
        """Sets the state of the checkboxes on all rows to agree with 'checkbox';
        the actual change is performed by row_updater, so this can be used for
        either checkbox."""
        if checkbox.get_visible():
            active = checkbox.get_active()
            self._setting_all_checkboxes = True

            for row in self.uninstall_game_list.get_children():
                row_updater(row, active)

            self._setting_all_checkboxes = False
            self.update_all_checkboxes()

    @GtkTemplate.Callback
    def on_cancel_button_clicked(self, _widget) -> None:
        self.destroy()

    @GtkTemplate.Callback
    def on_remove_button_clicked(self, _widget) -> None:
        rows = list(self.uninstall_game_list.get_children())
        delete_files_warning_games = [row.game for row in rows
                                      if row.delete_files and row.has_game_remove_warning]

        if delete_files_warning_games:
            if len(delete_files_warning_games) == 1:
                question = _(
                    "Please confirm.\nEverything under <b>%s</b>\n"
                    "will be moved to the trash."
                ) % gtk_safe(delete_files_warning_games[0].directory)
            else:
                question = _(
                    "Please confirm.\nAll the files for %d games will be moved to the trash."
                ) % len(delete_files_warning_games)

            dlg = QuestionDialog(
                {
                    "parent": self,
                    "question": question,
                    "title": _("Permanently delete files?"),
                }
            )

            if dlg.result != Gtk.ResponseType.YES:
                return

        for row in rows:
            row.perform_removal()

        self.destroy()

    def on_response(self, _dialog, response: Gtk.ResponseType) -> None:
        if response in (Gtk.ResponseType.DELETE_EVENT, Gtk.ResponseType.CANCEL, Gtk.ResponseType.OK):
            self.destroy()

    @staticmethod
    def _get_disk_size(directories: List[str]) -> Dict[str, int]:
        folder_sizes = {}
        for directory in directories:
            folder_sizes[directory] = get_disk_size(directory)
        return folder_sizes

    def _folder_size_cb(self, folder_sizes: Dict[str, int], error):
        if error:
            logger.error(error)
            return

        for row in self.uninstall_game_list.get_children():
            directory = row.game.directory
            if directory and directory in folder_sizes:
                size = folder_sizes[row.game.directory]
                row.show_folder_size(size)

    class GameRemovalRow(Gtk.ListBoxRow):
        def __init__(self, game: Game, can_delete_files: bool, checkbox_toggled_handler: Callable[[], None]):
            super().__init__(activatable=False)
            self.game = game
            self.can_delete_files = bool(can_delete_files and game.is_installed and game.directory)
            self.checkbox_toggled_handler = checkbox_toggled_handler
            self.delete_files_checkbox: Gtk.CheckButton = None
            self.folder_size_spinner: Gtk.Spinner = None

            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            vbox.pack_start(hbox, False, False, 0)

            label = Gtk.Label(game.name, selectable=True)
            hbox.pack_start(label, False, False, 0)

            self.delete_game_checkbox = Gtk.CheckButton("Remove from Library", active=False, halign=Gtk.Align.START)
            self.delete_game_checkbox.set_sensitive(game.is_installed)
            self.delete_game_checkbox.set_active(True)
            self.delete_game_checkbox.connect("toggled", self.on_checkbox_toggled)
            hbox.pack_end(self.delete_game_checkbox, False, False, 0)

            if game.is_installed and self.game.directory:
                delete_files_overlay = Gtk.Overlay(width_request=185)
                self.delete_files_checkbox = Gtk.CheckButton(_("Delete Files"))
                self.delete_files_checkbox.set_sensitive(can_delete_files)
                self.delete_files_checkbox.set_active(can_delete_files)
                self.delete_files_checkbox.set_tooltip_text(self.game.directory)
                self.delete_files_checkbox.connect("toggled", self.on_checkbox_toggled)
                delete_files_overlay.add(self.delete_files_checkbox)

                self.folder_size_spinner = Gtk.Spinner(visible=can_delete_files, no_show_all=True,
                                                       halign=Gtk.Align.END)
                if can_delete_files:
                    self.folder_size_spinner.start()
                delete_files_overlay.add_overlay(self.folder_size_spinner)
                hbox.pack_end(delete_files_overlay, False, False, 0)

                directory_label = Gtk.Label(halign=Gtk.Align.START,
                                            selectable=True,
                                            margin_left=6, margin_right=6)
                directory_label.set_markup("<span font_desc='8'>%s</span>" % gtk_safe(self.game.directory))
                vbox.pack_start(directory_label, False, False, 0)
            self.add(vbox)

        def on_checkbox_toggled(self, _widget):
            self.checkbox_toggled_handler()

        @property
        def can_show_folder_size(self) -> bool:
            return bool(self.folder_size_spinner)

        def show_folder_size(self, folder_size: int) -> None:
            """Called to stop the spinner and show the size of the game folder."""
            if self.delete_files_checkbox:
                self.delete_files_checkbox.set_label(_("Delete Files") + f" ({human_size(folder_size)})")

                if self.folder_size_spinner:
                    self.folder_size_spinner.stop()
                    self.folder_size_spinner.hide()

        @property
        def delete_files(self) -> bool:
            """True if the game files should be deleted."""
            return bool(self.game.is_installed and self.game.directory
                        and self.delete_files_checkbox.get_active())

        @delete_files.setter
        def delete_files(self, active: bool) -> None:
            self.delete_files_checkbox.set_active(active)

        @property
        def delete_game(self) -> bool:
            """True if the game should be rmoved from the PGA."""
            if not self.game.is_installed:
                return True

            return bool(self.delete_game_checkbox.get_active())

        @delete_game.setter
        def delete_game(self, active: bool) -> None:
            self.delete_game_checkbox.set_active(active)

        @property
        def has_game_remove_warning(self) -> bool:
            """True if the game should not provoke a warning before you delete its files."""
            return not hasattr(self.game.runner, "no_game_remove_warning")

        def perform_removal(self) -> None:
            """Performs the actions this row describes, uninstalling or deleting a game."""
            # We uninstall installed games, and delete games where self.delete_game is true;
            # but we must be careful to fire the game-removed single only once.
            if self.game.is_installed:
                if self.delete_game:
                    self.game.uninstall(delete_files=self.delete_files, no_signal=True)
                    self.game.delete()
                else:
                    self.game.uninstall(delete_files=self.delete_files)
            elif self.delete_game:
                self.game.delete()
