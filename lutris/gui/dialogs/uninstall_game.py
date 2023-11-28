# pylint: disable=no-member
import os
from gettext import gettext as _
from typing import Dict, List

from gi.repository import Gtk, Pango

from lutris.database.games import get_games
from lutris.exceptions import watch_errors
from lutris.game import Game
from lutris.gui import dialogs
from lutris.gui.dialogs import ModalDialog, QuestionDialog
from lutris.gui.widgets.gi_composites import GtkTemplate
from lutris.util import datapath
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import gtk_safe, human_size
from lutris.util.system import get_disk_size, is_removeable, path_exists, reverse_expanduser


class GameRemovalDialog(ModalDialog):
    def __init__(self,
                 title_markup: str,
                 delete_button_label: str,
                 parent=None):
        super().__init__(parent=parent, border_width=10)
        self.set_size_request(640, 128)

        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.delete_button = self.add_default_button(delete_button_label, Gtk.ResponseType.OK,
                                                     css_class="destructive-action")
        self.connect("response", self.on_response)

        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_bottom=4, visible=True)
        self.get_content_area().add(container)

        title_label = Gtk.Label(visible=True)
        title_label.set_line_wrap(True)
        title_label.set_alignment(0, 0.5)
        title_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_label.set_markup(title_markup)

        container.pack_start(title_label, False, False, 0)

        self.message_label = Gtk.Label(visible=True, no_show_all=True)
        self.message_label.set_alignment(0, 0.5)

        container.pack_start(self.message_label, False, False, 0)

        delete_files_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, visible=True)
        self.delete_files_checkbox = Gtk.CheckButton(visible=False, no_show_all=True)
        self.delete_files_checkbox.set_active(True)
        self.delete_files_spinner = Gtk.Spinner(visible=False, no_show_all=True)
        delete_files_box.pack_start(self.delete_files_checkbox, False, False, 0)
        delete_files_box.pack_start(self.delete_files_spinner, False, False, 0)
        container.pack_start(delete_files_box, False, False, 0)

    def on_response(self, _widget, response):
        if response == Gtk.ResponseType.OK:
            self.delete_button.set_sensitive(False)

            delete_files = (self.delete_files_checkbox.get_active()
                            and self.delete_files_checkbox.get_visible())

            if not self.perform_removal(delete_files):
                self.delete_button.set_sensitive(True)
                return True
        self.destroy()

    def perform_removal(self, delete_files: bool) -> bool:
        raise NotImplementedError

    def show_message_label(self, markup: str) -> None:
        self.message_label.set_markup(markup)
        self.message_label.show()

    def hide_message_label(self):
        self.message_label.hide()

    def show_delete_files_spinner(self, label: str) -> None:
        self.delete_files_checkbox.set_sensitive(False)
        self.delete_files_checkbox.set_active(False)
        self.delete_files_checkbox.set_label(label)
        self.delete_files_checkbox.show()
        self.delete_files_spinner.show()
        self.delete_files_spinner.start()

    def show_delete_files_checkbox(self, active: bool, label: str) -> None:
        self.delete_files_checkbox.set_sensitive(True)
        self.delete_files_checkbox.set_active(active)
        self.delete_files_checkbox.set_label(label)
        self.delete_files_checkbox.show()
        self.delete_files_spinner.stop()
        self.delete_files_spinner.hide()


class UninstallGameDialog(GameRemovalDialog):
    def __init__(self, game_id: str, parent=None):
        self.game = Game(game_id)
        title_markup = _("<span font_desc='14'><b>Uninstall %s</b></span>") % gtk_safe(self.game.name)
        super().__init__(title_markup=title_markup,
                         delete_button_label=_("Uninstall"),
                         parent=parent)

        if not self.game.directory:
            self.show_message_label(_("No file will be deleted"))
        elif len(get_games(filters={"directory": self.game.directory})) > 1:
            self.show_message_label(
                _("The folder %s is used by other games and will be kept.") % self.game.directory)
        elif self.game.config and is_removeable(self.game.directory, self.game.config.system_config):
            self.delete_button.set_sensitive(False)
            self.show_delete_files_spinner(_("Calculating size…"))
            AsyncCall(get_disk_size, self.folder_size_cb, self.game.directory)
        elif not path_exists(self.game.directory):
            self.show_message_label(
                _("%s does not exist.") % reverse_expanduser(self.game.directory)
            )
        else:
            self.show_message_label(
                _("Content of %s are protected and will not be deleted.") % reverse_expanduser(self.game.directory)
            )

    def folder_size_cb(self, folder_size, error):
        if error:
            logger.error(error)
            return
        self.delete_button.set_sensitive(True)
        self.show_delete_files_checkbox(
            active=True,
            label=_("Delete %s (%s)") % (
                reverse_expanduser(self.game.directory),
                human_size(folder_size)
            )
        )
        self.hide_message_label()

    def perform_removal(self, delete_files: bool) -> bool:
        if delete_files and not hasattr(self.game.runner, "no_game_remove_warning"):
            dlg = QuestionDialog(
                {
                    "parent": self,
                    "question": _(
                        "Please confirm.\nEverything under <b>%s</b>\n"
                        "will be deleted."
                    ) % gtk_safe(self.game.directory),
                    "title": _("Permanently delete files?"),
                }
            )
            if dlg.result != Gtk.ResponseType.YES:
                return False
        if delete_files:
            self.show_message_label(_("Uninstalling game and deleting files..."))
        else:
            self.show_message_label(_("Uninstalling game..."))
        self.game.remove(delete_files)
        return True


class RemoveGameDialog(GameRemovalDialog):
    def __init__(self, game_id: str, parent=None):
        self.game = Game(game_id)
        title_markup = _("<span font_desc='14'><b>Remove %s</b></span>") % gtk_safe(self.game.name)
        super().__init__(title_markup=title_markup,
                         delete_button_label=_("Remove"),
                         parent=parent)

        self.show_message_label(
            _("Completely remove %s from the library?\nAll play time will be lost.") % self.game)

    def perform_removal(self, delete_files: bool) -> bool:
        self.game.delete()
        return True


class RemoveMultipleGamesDialog0(GameRemovalDialog):
    def __init__(self, game_ids: List[str], parent=None):
        self.games = [Game(game_id) for game_id in game_ids]
        self.to_uninstall = [g for g in self.games if g.is_installed]
        self.to_remove = [g for g in self.games if not g.is_installed]

        if self.to_remove:
            title_markup = _("<span font_desc='14'><b>Remove %d games</b></span>") % len(self.games)
        else:
            title_markup = _("<span font_desc='14'><b>Uninstall %d games</b></span>") % len(self.games)

        super().__init__(title_markup=title_markup,
                         delete_button_label=_("Remove") if self.to_remove else _("Uninstall"),
                         parent=parent)

        message = ""

        if self.to_uninstall:
            message += _("%d installed games will be uninstalled.\n") % len(self.to_uninstall)

        if self.to_remove:
            message += _("%d uninstalled games will be removed, and their playtimes will be lost.\n") % len(
                self.to_remove)

        self.show_message_label(message.strip())
        self.start_folder_size_check()

    def start_folder_size_check(self) -> None:
        uninstallable = [g for g in self.to_uninstall
                         if g.config and is_removeable(g.directory, g.config.system_config)]

        def is_shared(directory: str) -> bool:
            dir_users = set(str(g["id"]) for g in get_games(filters={"directory": directory}))
            for g in uninstallable:
                dir_users.discard(g.id)
            return bool(dir_users)

        directories = [g.directory for g in uninstallable
                       if g.directory and not is_shared(g.directory)]

        if directories:
            self.delete_button.set_sensitive(False)
            self.show_delete_files_spinner(_("Calculating size…"))
            AsyncCall(self._get_disk_size, self._folder_size_cb, directories)

    @staticmethod
    def _get_disk_size(directories: List[str]) -> int:
        total = 0
        for directory in directories:
            total += get_disk_size(directory)
        return total

    def _folder_size_cb(self, folder_size, error):
        if error:
            logger.error(error)
            return
        self.delete_button.set_sensitive(True)
        self.show_delete_files_checkbox(
            active=True,
            label=_("Delete game directories (%s)") % human_size(folder_size)
        )

    def perform_removal(self, delete_files: bool) -> bool:
        if delete_files and any(g for g in self.to_uninstall
                                if not hasattr(g.runner, "no_game_remove_warning")):
            dlg = QuestionDialog(
                {
                    "parent": self,
                    "question": _(
                        "Please confirm.\nEverything in the game directories of these games\n"
                        "will be deleted."
                    ),
                    "title": _("Permanently delete files?"),
                }
            )
            if dlg.result != Gtk.ResponseType.YES:
                return False

        if delete_files:
            self.show_message_label(_("Uninstalling game and deleting files..."))
        else:
            self.show_message_label(_("Uninstalling games..."))

        for game in self.to_uninstall:
            game.remove(delete_files)

        self.show_message_label(_("Removing games..."))

        for game in self.to_remove:
            game.delete()

        return True


@GtkTemplate(ui=os.path.join(datapath.get(), "ui", "uninstall-dialog.ui"))
class RemoveMultipleGamesDialog(Gtk.Dialog):
    __gtype_name__ = "RemoveMultipleGamesDialog"

    cancel_button: Gtk.Button = GtkTemplate.Child()
    remove_button: Gtk.Button = GtkTemplate.Child()
    uninstall_game_list: Gtk.ListBox = GtkTemplate.Child()

    def __init__(self, game_ids: List[str], parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.games = [Game(game_id) for game_id in game_ids]

        self.init_template()

        for game in self.games:
            row = RemoveMultipleGamesDialog.GameRemovalRow(game)
            self.uninstall_game_list.add(row)

        folders_to_size = [row.game.directory for row
                           in self.uninstall_game_list.get_children()
                           if row.can_show_folder_size]

        if folders_to_size:
            AsyncCall(self._get_disk_size, self._folder_size_cb, folders_to_size)

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
        def __init__(self, game):
            super().__init__()
            self.game = game
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            label = Gtk.Label(game.name)
            box.pack_start(label, False, False, 0)
            self.keep_files_checkbox = None
            self.keep_playtime_checkbox = None
            self.folder_size_label = None

            if game.is_installed:
                self.folder_size_label = Gtk.Label("", no_show_all=True, width_request=50)
                self.folder_size_spinner = Gtk.Spinner(width_request=50)
                self.folder_size_spinner.start()
                box.pack_end(self.folder_size_spinner, False, False, 0)
                box.pack_end(self.folder_size_label, False, False, 0)

                self.keep_files_checkbox = Gtk.CheckButton("Keep Files")
                box.pack_end(self.keep_files_checkbox, False, False, 0)

                if game.playtime:
                    self.keep_playtime_checkbox = Gtk.CheckButton("Keep Playtime", active=True)
                    box.pack_end(self.keep_playtime_checkbox, False, False, 0)

            self.add(box)

        @property
        def can_show_folder_size(self):
            return bool(self.folder_size_label)

        def show_folder_size(self, folder_size: int):
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
