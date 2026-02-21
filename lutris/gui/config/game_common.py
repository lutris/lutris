"""Shared config dialog stuff"""

# pylint: disable=not-an-iterable
from gettext import gettext as _

from gi.repository import Gtk

from lutris import settings
from lutris.config import LutrisConfig, make_game_config_id, rename_config
from lutris.game import Game
from lutris.gui.config import DIALOG_HEIGHT, DIALOG_WIDTH
from lutris.gui.config.boxes import GameBox, RunnerBox, SystemConfigBox
from lutris.gui.config.game_info_box import GameInfoBox
from lutris.gui.config.widget_generator import WidgetWarningMessageBox
from lutris.gui.dialogs import DirectoryDialog, ErrorDialog, QuestionDialog, SavableModelessDialog, display_error
from lutris.gui.dialogs.delegates import DialogInstallUIDelegate
from lutris.gui.dialogs.move_game import MoveDialog
from lutris.gui.widgets.notifications import send_notification
from lutris.runners import import_runner
from lutris.services.lutris import download_lutris_media
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import parse_playtime, slugify


# pylint: disable=too-many-instance-attributes, no-member
class GameDialogCommon(SavableModelessDialog, DialogInstallUIDelegate):  # type:ignore[misc]
    """Base class for config dialogs"""

    no_runner_label = _("Select a runner in the Game Info tab")

    def __init__(self, title, config_level, parent=None):
        super().__init__(title, parent=parent, border_width=0)
        self.config_level = config_level
        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)
        self.vbox.set_border_width(0)

        self.notebook = None

        self.info_box = None
        self.runner_box = None

        self.timer_id = None
        self.game = None
        self.saved = None
        self.option_page_indices = set()
        self.searchable_page_indices = set()
        self.advanced_switch_widgets = []
        self.header_bar_widgets = []
        self.game_box = None
        self.system_box = None
        self.runner_name = None
        self.lutris_config = None
        self.notebook_page_generators = {}
        self.notebook_page_updater = {}

        self.build_header_bar()

    @staticmethod
    def build_scrolled_window(widget):
        """Return a scrolled window containing config widgets"""
        scrolled_window = Gtk.ScrolledWindow(visible=True)
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(widget)
        return scrolled_window

    def build_notebook(self):
        self.notebook = Gtk.Notebook(visible=True)
        self.notebook.set_show_border(False)
        self.notebook.connect("switch-page", self.on_notebook_switch_page)
        self.vbox.pack_start(self.notebook, True, True, 0)

    def on_notebook_switch_page(self, notebook, page, index):
        generator = self.notebook_page_generators.get(index)
        if generator:
            generator()
            del self.notebook_page_generators[index]
        else:
            updater = self.notebook_page_updater.get(index)
            if updater:
                updater()

        self.update_advanced_switch_visibility(index)
        self.update_search_entry_visibility(index)

    def build_tabs(self):
        """Build tabs (for game and runner levels)"""
        self.timer_id = None
        if self.config_level == "game":
            self._build_info_tab()
            self._build_game_tab()
        self._build_runner_tab()
        self._build_system_tab()

        current_page_index = self.notebook.get_current_page()
        self.update_advanced_switch_visibility(current_page_index)
        self.update_search_entry_visibility(current_page_index)

    def set_header_bar_widgets_visibility(self, value):
        for widget in self.header_bar_widgets:
            widget.set_visible(value)

    def update_advanced_switch_visibility(self, current_page_index):
        if self.notebook:
            show_switch = current_page_index in self.option_page_indices
            for widget in self.advanced_switch_widgets:
                widget.set_visible(show_switch)

    def update_search_entry_visibility(self, current_page_index):
        """Shows or hides the search entry according to what page is currently displayed."""
        if self.notebook:
            show_search = current_page_index in self.searchable_page_indices
            self.set_search_entry_visibility(show_search)

    def set_search_entry_visibility(self, show_search, placeholder_text=None, tooltip_markup=None):
        """Explicitly shows or hides the search entry; can also update the placeholder text."""
        header_bar = self.get_header_bar()
        if show_search and self.search_entry:
            header_bar.set_custom_title(self.search_entry)
            self.search_entry.set_placeholder_text(placeholder_text or self.get_search_entry_placeholder())
            self.search_entry.set_tooltip_markup(tooltip_markup)
        else:
            header_bar.set_custom_title(None)

    def get_search_entry_placeholder(self):
        if self.game and self.game.name:
            return _("Search %s options") % self.game.name

        return _("Search options")

    def _build_info_tab(self):
        self.info_box = GameInfoBox(parent_widget=self, game=self.game)

        info_sw = self.build_scrolled_window(self.info_box)
        page_index = self._add_notebook_tab(info_sw, _("Game info"))
        self.option_page_indices.add(page_index)

    def on_move_clicked(self, _button):
        game_directory = self.game.directory if self.game else ""
        new_location = DirectoryDialog("Select new location for the game", default_path=game_directory, parent=self)
        if not new_location.folder or new_location.folder == game_directory:
            return
        move_dialog = MoveDialog(self.game, new_location.folder, parent=self)
        move_dialog.connect("game-moved", self.on_game_moved)
        move_dialog.move()

    def on_game_moved(self, dialog):
        """Show a notification when the game is moved"""
        new_directory = dialog.new_directory
        if new_directory:
            self.game = Game(self.game.id if self.game else None)
            self.lutris_config = self.game.config
            self._rebuild_tabs()
            if self.info_box.directory_entry:
                self.info_box.directory_entry.set_text(new_directory)
            send_notification("Finished moving game", "%s moved to %s" % (dialog.game, new_directory))
        else:
            send_notification("Failed to move game", "Lutris could not move %s" % dialog.game)

    def _build_game_tab(self):
        def is_searchable(game):
            return game.has_runner and len(game.runner.game_options) > 8

        def has_advanced(game):
            if game.has_runner:
                for opt in game.runner.game_options:
                    if opt.get("advanced"):
                        return True
            return False

        if self.game and self.runner_name:
            self.game.runner_name = self.runner_name
            self.game_box = self._build_options_tab(
                _("Game options"),
                lambda: GameBox(self.config_level, self.lutris_config, self.game),
                advanced=has_advanced(self.game),
                searchable=is_searchable(self.game),
            )
        elif self.runner_name:
            game = Game(None)
            game.runner_name = self.runner_name
            self.game_box = self._build_options_tab(
                _("Game options"),
                lambda: GameBox(self.config_level, self.lutris_config, game),
                advanced=has_advanced(game),
                searchable=is_searchable(game),
            )
        else:
            self._build_missing_options_tab(self.no_runner_label, _("Game options"))

    def _build_runner_tab(self):
        if self.runner_name:
            self.runner_box = self._build_options_tab(
                _("Runner options"), lambda: RunnerBox(self.config_level, self.lutris_config)
            )
        else:
            self._build_missing_options_tab(self.no_runner_label, _("Runner options"))

    def _build_system_tab(self):
        self.system_box = self._build_options_tab(
            _("System options"), lambda: SystemConfigBox(self.config_level, self.lutris_config)
        )

    def _build_options_tab(self, notebook_label, box_factory, advanced=True, searchable=True):
        if not self.lutris_config:
            raise RuntimeError("Lutris config not loaded yet")
        config_box = box_factory()
        page_index = self._add_notebook_tab(self.build_scrolled_window(config_box), notebook_label)

        self.notebook_page_updater[page_index] = config_box.update_widgets

        if page_index == 0:
            config_box.generate_widgets()
        else:
            self.notebook_page_generators[page_index] = config_box.generate_widgets

        if advanced:
            self.option_page_indices.add(page_index)
        if searchable:
            self.searchable_page_indices.add(page_index)
        return config_box

    def _build_missing_options_tab(self, missing_label, notebook_label):
        label = Gtk.Label(label=self.no_runner_label)
        page_index = self._add_notebook_tab(label, notebook_label)
        self.option_page_indices.add(page_index)

    def _add_notebook_tab(self, widget, label):
        return self.notebook.append_page(widget, Gtk.Label(label=label))

    def build_header_bar(self):
        self.search_entry = Gtk.SearchEntry(width_chars=30, placeholder_text=_("Search options"))
        self.search_entry.connect("search-changed", self.on_search_entry_changed)
        self.search_entry.show_all()

        # Advanced settings toggle
        switch_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5, no_show_all=True, visible=True)
        switch_box.set_tooltip_text(_("Show advanced options"))

        switch_label = Gtk.Label(_("Advanced"), no_show_all=True, visible=True)
        switch = Gtk.Switch(no_show_all=True, visible=True, valign=Gtk.Align.CENTER)
        switch.set_state(settings.read_setting("show_advanced_options") == "True")
        switch.connect("state-set", lambda _w, s: self.on_show_advanced_options_toggled(bool(s)))

        switch_box.pack_start(switch_label, False, False, 0)
        switch_box.pack_end(switch, False, False, 0)

        header_bar = self.get_header_bar()

        header_bar.pack_end(switch_box)

        # These lists need to be distinct, so they can be separately
        # hidden or shown without interfering with each other.
        self.advanced_switch_widgets = [switch_label, switch]
        self.header_bar_widgets = [self.cancel_button, self.save_button, switch_box]

        if self.notebook:
            self.update_advanced_switch_visibility(self.notebook.get_current_page())

    def on_search_entry_changed(self, entry):
        """Callback for the search input keypresses"""
        text = entry.get_text().lower().strip()
        self._set_filter(text)

    def on_show_advanced_options_toggled(self, is_active):
        settings.write_setting("show_advanced_options", is_active)

        self._set_advanced_options_visible(is_active)

    def _set_advanced_options_visible(self, value):
        """Change visibility of advanced options across all config tabs."""
        if self.info_box:
            self.info_box.advanced_visibility = value
        if self.system_box:
            self.system_box.advanced_visibility = value
        if self.runner_box:
            self.runner_box.advanced_visibility = value
        if self.game_box:
            self.game_box.advanced_visibility = value

    def _set_filter(self, value):
        if self.system_box:
            self.system_box.filter = value
        if self.runner_box:
            self.runner_box.filter = value
        if self.game_box:
            self.game_box.filter = value

    def on_runner_changed(self, widget):
        """Action called when runner drop down is changed."""
        new_runner_index = widget.get_active()
        game_info_box = self.info_box
        if game_info_box.runner_index and new_runner_index != game_info_box.runner_index:
            dlg = QuestionDialog(
                {
                    "parent": self,
                    "question": _(
                        "Are you sure you want to change the runner for this game ? "
                        "This will reset the full configuration for this game and "
                        "is not reversible."
                    ),
                    "title": _("Confirm runner change"),
                }
            )

            if dlg.result == Gtk.ResponseType.YES:
                self._switch_runner(widget, new_runner_index)
            else:
                # Revert the dropdown menu to the previously selected runner
                widget.set_active(game_info_box.runner_index)
        else:
            self._switch_runner(widget, new_runner_index)

    def _switch_runner(self, widget, new_runner_index):
        """Rebuilds the UI on runner change"""
        current_page = self.notebook.get_current_page()
        game_info_box = self.info_box
        game_info_box.runner_index = new_runner_index
        if new_runner_index == 0:
            logger.info("No runner selected, resetting configuration")
            self.runner_name = None
            self.lutris_config = None
        else:
            runner_name = widget.get_model()[new_runner_index][1]
            if runner_name == self.runner_name:
                logger.debug("Runner unchanged, not creating a new config")
                return
            logger.info("Creating new configuration with runner %s", runner_name)
            self.runner_name = runner_name
            self.lutris_config = LutrisConfig(runner_slug=self.runner_name, level="game")
        self._rebuild_tabs()
        self.notebook.set_current_page(current_page)

    def _rebuild_tabs(self):
        """Rebuild notebook pages"""
        for i in range(self.notebook.get_n_pages(), 1, -1):
            self.notebook.remove_page(i - 1)
        self.option_page_indices.clear()
        self.searchable_page_indices.clear()
        self._build_game_tab()
        self._build_runner_tab()
        self._build_system_tab()
        self.show_all()

    def on_response(self, _widget, response):
        if response in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.DELETE_EVENT):
            # Reload the config to clean out any changes we may have made
            if self.game:
                self.game.reload_config()
        super().on_response(_widget, response)

    def is_valid(self) -> bool:
        game_info_box = self.info_box
        if not self.runner_name:
            ErrorDialog(_("Runner not provided"), parent=self)
            return False
        if not game_info_box.name_entry.get_text():
            ErrorDialog(_("Please fill in the name"), parent=self)
            return False
        if self.runner_name == "steam" and not self.lutris_config.game_config.get("appid"):
            ErrorDialog(_("Steam AppID not provided"), parent=self)
            return False
        playtime_text = game_info_box.playtime_entry.get_text()
        if playtime_text and (not self.game or playtime_text != self.game.formatted_playtime):
            try:
                parse_playtime(playtime_text)
            except ValueError as ex:
                display_error(ex, parent=self)
                return False

        invalid_fields = []
        runner_class = import_runner(self.runner_name)
        runner_instance = runner_class()
        for config in ["game", "runner"]:
            for k, v in getattr(self.lutris_config, config + "_config").items():
                option = runner_instance.find_option(config + "_options", k)
                if option is None:
                    continue
                validator = option.get("validator")
                if validator is not None:
                    try:
                        res = validator(v)
                        logger.debug("%s validated successfully: %s", k, res)
                    except Exception:
                        invalid_fields.append(option.get("label"))
        if invalid_fields:
            ErrorDialog(_("The following fields have invalid values: ") + ", ".join(invalid_fields), parent=self)
            return False
        return True

    def on_save(self, _button):
        """Save game info and destroy widget."""
        if not self.is_valid():
            logger.warning(_("Current configuration is not valid, ignoring save request"))
            return
        game_info_box = self.info_box
        name = game_info_box.name_entry.get_text()
        sortname = game_info_box.sortname_entry.get_text()

        if not game_info_box.slug:
            game_info_box.slug = slugify(name)
        if game_info_box.slug != game_info_box.initial_slug:
            AsyncCall(download_lutris_media, None, game_info_box.slug)
        if not self.game:
            self.game = Game()

        year = None
        if game_info_box.year_entry.get_text():
            year = int(game_info_box.year_entry.get_text())

        playtime = None
        playtime_text = game_info_box.playtime_entry.get_text()
        if playtime_text and playtime_text != self.game.formatted_playtime:
            playtime = parse_playtime(playtime_text)

        if not self.lutris_config.game_config_id:
            self.lutris_config.game_config_id = make_game_config_id(game_info_box.slug)

        self.game.name = name
        self.game.sortname = sortname
        self.game.slug = game_info_box.slug
        self.game.year = year
        if playtime:
            self.game.playtime = playtime
        self.game.is_installed = True
        self.game.config = self.lutris_config

        # Rename config file if game slug changed
        if new_config_id := rename_config(self.game.config.game_config_id, self.game.slug):
            self.game.config.game_config_id = new_config_id

        self.game.runner_name = self.runner_name

        if "icon" not in self.game.custom_images:
            self.game.runner.extract_icon(game_info_box.slug)

        self.game.save()
        self.destroy()
        self.saved = True
        return True


class RunnerMessageBox(WidgetWarningMessageBox):
    def __init__(self):
        super().__init__(margin_left=12, margin_right=12, icon_name="dialog-warning")
