# pylint: disable=no-member
import os
from gettext import gettext as _
from typing import Dict, List

from gi.repository import Gtk

from lutris.database.games import get_games
from lutris.exceptions import watch_errors
from lutris.game import Game
from lutris.gui import dialogs
from lutris.gui.dialogs import QuestionDialog
from lutris.gui.widgets.gi_composites import GtkTemplate
from lutris.util import datapath
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import gtk_safe, human_size
from lutris.util.system import get_disk_size, is_removeable


@GtkTemplate(ui=os.path.join(datapath.get(), "ui", "uninstall-dialog.ui"))
class UninstallMultipleGamesDialog(Gtk.Dialog):
    __gtype_name__ = "UninstallMultipleGamesDialog"

    header_bar: Gtk.HeaderBar = GtkTemplate.Child()
    message_label: Gtk.Label = GtkTemplate.Child()
    uninstall_game_list: Gtk.ListBox = GtkTemplate.Child()
    cancel_button: Gtk.Button = GtkTemplate.Child()
    uninstall_button: Gtk.Button = GtkTemplate.Child()

    def __init__(self, game_ids: List[str], parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.games = [Game(game_id) for game_id in game_ids]
        to_uninstall = [g for g in self.games if g.is_installed]
        to_remove = [g for g in self.games if not g.is_installed]

        if len(to_uninstall) == 1 and not to_remove:
            game = to_uninstall[0]
            subtitle = _("Uninstall %s") % gtk_safe(game.name)
        elif len(to_remove) == 1 and not to_uninstall:
            game = to_remove[0]
            subtitle = _("Remove %s") % gtk_safe(game.name)
        elif not to_remove:
            subtitle = _("Uninstall %d games") % len(to_uninstall)
        elif not to_uninstall:
            subtitle = _("Uninstall %d games") % len(to_remove)
        else:
            subtitle = _("Uninstall %d games and remove %d games") % (
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
        any_shared = False
        any_protected = False
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

            row = UninstallMultipleGamesDialog.GameRemovalRow(game, can_delete_files)

            if can_delete_files and row.can_show_folder_size:
                folders_to_size.append(game.directory)

            self.uninstall_game_list.add(row)

        if folders_to_size:
            AsyncCall(self._get_disk_size, self._folder_size_cb, folders_to_size)

        messages = []

        if to_uninstall:
            messages.append(_("After you uninstall these games, you won't be able play them in Lutris. "
                              "You can select data you wish to keep."))
        else:
            messages.append(_("After you remove these games, they will no longer "
                              "appear in the 'Games' view."))

        if any_shared:
            messages.append(_("Some of the game directories cannot be removed because they are shared "
                              "with other games that you are not removing."))

        if any_protected:
            messages.append(_("Some of the game directories cannot be removed because they are protected."))

        self.header_bar.set_subtitle(subtitle)

        if messages:
            self.message_label.set_markup("\n\n".join(messages))
            self.message_label.show()
        else:
            self.message_label.hide()

        self.show_all()
        self.connect("response", self.on_response)

    @watch_errors()
    @GtkTemplate.Callback
    def on_cancel_button_clicked(self, _widget):
        self.destroy()

    @watch_errors()
    @GtkTemplate.Callback
    def on_remove_button_clicked(self, _widget):
        rows = list(self.uninstall_game_list.get_children())
        delete_files_warning_games = [row.game for row in rows
                                      if row.delete_files and row.has_game_remove_warning]

        if delete_files_warning_games:
            if len(delete_files_warning_games) == 1:
                question = _(
                    "Please confirm.\nEverything under <b>%s</b>\n"
                    "will be deleted."
                ) % gtk_safe(delete_files_warning_games[0].directory)
            else:
                question = _(
                    "Please confirm.\nAll the files for %d games will be deleted."
                ) % len(delete_files_warning_games)

            dlg = QuestionDialog(
                {
                    "parent": self,
                    "question": question,
                    "title": _("Permanently delete files?"),
                }
            )

            if dlg.result != Gtk.ResponseType.YES:
                return False

        for row in rows:
            row.perform_removal()

        self.destroy()

    def on_response(self, _dialog, response):
        if response in (Gtk.ResponseType.DELETE_EVENT, Gtk.ResponseType.CANCEL, Gtk.ResponseType.OK):
            self.destroy()

    @staticmethod
    def _get_disk_size(directories: List[str]) -> Dict[str, int]:
        folder_sizes = {}
        for directory in directories:
            folder_sizes[directory] = get_disk_size(directory)
        return folder_sizes

    def _folder_size_cb(self, folder_sizes, error):
        if error:
            logger.error(error)
            return

        for row in self.uninstall_game_list.get_children():
            directory = row.game.directory
            if directory and directory in folder_sizes:
                size = folder_sizes[row.game.directory]
                row.show_folder_size(size)

    class GameRemovalRow(Gtk.ListBoxRow):
        def __init__(self, game: Game, can_delete_files: bool):
            super().__init__()
            self.game = game
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            label = Gtk.Label(game.name)
            box.pack_start(label, False, False, 0)
            self.keep_files_checkbox = None
            self.keep_playtime_checkbox = None
            self.folder_size_label = None

            if game.is_installed:
                if self.game.directory:
                    folder_size_width = 75
                    self.folder_size_label = Gtk.Label("", xalign=0,
                                                       visible=not can_delete_files, no_show_all=True,
                                                       width_request=folder_size_width)
                    self.folder_size_spinner = Gtk.Spinner(visible=can_delete_files, no_show_all=True,
                                                           width_request=folder_size_width)
                    if can_delete_files:
                        self.folder_size_spinner.start()
                    box.pack_end(self.folder_size_spinner, False, False, 0)
                    box.pack_end(self.folder_size_label, False, False, 0)

                    self.keep_files_checkbox = Gtk.CheckButton("Keep Files")
                    self.keep_files_checkbox.set_sensitive(can_delete_files)
                    self.keep_files_checkbox.set_active(not can_delete_files)
                    box.pack_end(self.keep_files_checkbox, False, False, 0)

                if game.playtime:
                    self.keep_playtime_checkbox = Gtk.CheckButton("Keep Playtime", active=True)
                    box.pack_end(self.keep_playtime_checkbox, False, False, 0)

            self.add(box)

        @property
        def can_show_folder_size(self):
            return bool(self.folder_size_label)

        def show_folder_size(self, folder_size: int):
            if self.folder_size_label:
                self.folder_size_label.set_text(human_size(folder_size))
                self.folder_size_label.show()
                self.folder_size_spinner.stop()
                self.folder_size_spinner.hide()

        @property
        def delete_files(self):
            if not self.game.is_installed:
                return False

            return self.keep_files_checkbox and not self.keep_files_checkbox.get_active()

        @property
        def keep_playtime(self):
            if not self.game.is_installed:
                return False

            return self.keep_playtime_checkbox and self.keep_playtime_checkbox.get_active()

        @property
        def has_game_remove_warning(self):
            return not hasattr(self.game.runner, "no_game_remove_warning")

        def perform_removal(self):
            if self.game.is_installed:
                if self.keep_playtime:
                    self.game.remove(self.delete_files)
                else:
                    self.game.remove(self.delete_files, no_signal=True)
                    self.game.delete()
            else:
                self.game.delete()

    def on_watched_error(self, error):
        dialogs.ErrorDialog(error, parent=self)
