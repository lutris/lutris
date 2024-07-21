"""Shared config dialog stuff"""

# pylint: disable=not-an-iterable
import os.path
import shutil
from gettext import gettext as _

from gi.repository import GdkPixbuf, Gtk, Pango

from lutris import runners, settings
from lutris.config import LutrisConfig, make_game_config_id
from lutris.game import Game
from lutris.gui.config import DIALOG_HEIGHT, DIALOG_WIDTH
from lutris.gui.config.boxes import GameBox, RunnerBox, SystemConfigBox, UnderslungMessageBox
from lutris.gui.dialogs import DirectoryDialog, ErrorDialog, QuestionDialog, SavableModelessDialog, display_error
from lutris.gui.dialogs.delegates import DialogInstallUIDelegate
from lutris.gui.dialogs.move_game import MoveDialog
from lutris.gui.widgets.common import Label, NumberEntry, SlugEntry
from lutris.gui.widgets.notifications import send_notification
from lutris.gui.widgets.scaled_image import ScaledImage
from lutris.gui.widgets.utils import MEDIA_CACHE_INVALIDATED, get_image_file_extension
from lutris.runners import import_runner
from lutris.services.lutris import LutrisBanner, LutrisCoverart, LutrisIcon, download_lutris_media
from lutris.services.service_media import resolve_media_path
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import gtk_safe, parse_playtime, slugify


# pylint: disable=too-many-instance-attributes, no-member
class GameDialogCommon(SavableModelessDialog, DialogInstallUIDelegate):
    """Base class for config dialogs"""

    no_runner_label = _("Select a runner in the Game Info tab")

    def __init__(self, title, config_level, parent=None):
        super().__init__(title, parent=parent, border_width=0)
        self.config_level = config_level
        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)
        self.vbox.set_border_width(0)

        self.notebook = None
        self.name_entry = None
        self.sortname_entry = None
        self.runner_box = None
        self.runner_warning_box = None

        self.timer_id = None
        self.game = None
        self.saved = None
        self.slug = None
        self.initial_slug = None
        self.slug_entry = None
        self.directory_entry = None
        self.year_entry = None
        self.playtime_entry = None
        self.slug_change_button = None
        self.runner_dropdown = None
        self.image_buttons = {}
        self.option_page_indices = set()
        self.searchable_page_indices = set()
        self.advanced_switch_widgets = []
        self.header_bar_widgets = []
        self.game_box = None
        self.system_box = None
        self.runner_name = None
        self.runner_index = None
        self.lutris_config = None
        self.service_medias = {"icon": LutrisIcon(), "banner": LutrisBanner(), "coverart_big": LutrisCoverart()}
        self.notebook_page_generators = {}

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
        info_box = Gtk.VBox()

        if self.game:
            centering_container = Gtk.HBox()
            banner_box = self._get_banner_box()
            centering_container.pack_start(banner_box, True, False, 0)
            info_box.pack_start(centering_container, False, False, 0)  # Banner

        info_box.pack_start(self._get_name_box(), False, False, 6)  # Game name
        info_box.pack_start(self._get_sortname_box(), False, False, 6)  # Game sort name

        self.runner_box = self._get_runner_box()
        info_box.pack_start(self.runner_box, False, False, 6)  # Runner

        self.runner_warning_box = RunnerMessageBox()
        info_box.pack_start(self.runner_warning_box, False, False, 6)  # Runner
        self.runner_warning_box.update_warning(self.runner_name)

        info_box.pack_start(self._get_year_box(), False, False, 6)  # Year

        info_box.pack_start(self._get_playtime_box(), False, False, 6)  # Playtime

        if self.game:
            info_box.pack_start(self._get_slug_box(), False, False, 6)
            info_box.pack_start(self._get_directory_box(), False, False, 6)
            info_box.pack_start(self._get_launch_config_box(), False, False, 6)

        info_sw = self.build_scrolled_window(info_box)
        self._add_notebook_tab(info_sw, _("Game info"))

    def _get_name_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Name"))
        box.pack_start(label, False, False, 0)
        self.name_entry = Gtk.Entry()
        self.name_entry.set_max_length(150)
        if self.game:
            self.name_entry.set_text(self.game.name)
        box.pack_start(self.name_entry, True, True, 0)
        return box

    def _get_sortname_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Sort name"))
        box.pack_start(label, False, False, 0)
        self.sortname_entry = Gtk.Entry()
        self.sortname_entry.set_max_length(150)
        if self.game:
            self.sortname_entry.set_placeholder_text(self.game.name)
            if self.game.sortname:
                self.sortname_entry.set_text(self.game.sortname)
        box.pack_start(self.sortname_entry, True, True, 0)
        return box

    def _get_slug_box(self):
        slug_box = Gtk.VBox(spacing=12, margin_right=12, margin_left=12)

        slug_entry_box = Gtk.Box(spacing=12, margin_right=0, margin_left=0)
        slug_label = Label()
        slug_label.set_markup(_("Identifier\n<span size='x-small'>(Internal ID: %s)</span>") % self.game.id)
        slug_entry_box.pack_start(slug_label, False, False, 0)

        self.slug_entry = SlugEntry()
        self.slug_entry.set_text(self.game.slug)
        self.slug_entry.set_sensitive(False)
        self.slug_entry.connect("activate", self.on_slug_entry_activate)
        slug_entry_box.pack_start(self.slug_entry, True, True, 0)

        self.slug_change_button = Gtk.Button(_("Change"))
        self.slug_change_button.connect("clicked", self.on_slug_change_clicked)
        slug_entry_box.pack_start(self.slug_change_button, False, False, 0)

        slug_box.pack_start(slug_entry_box, True, True, 0)

        return slug_box

    def _get_directory_box(self):
        """Return widget displaying the location of the game and allowing to move it"""
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12, visible=True)
        label = Label(_("Directory"))
        box.pack_start(label, False, False, 0)
        self.directory_entry = Gtk.Entry(visible=True)
        self.directory_entry.set_text(self.game.directory)
        self.directory_entry.set_sensitive(False)
        box.pack_start(self.directory_entry, True, True, 0)
        move_button = Gtk.Button(_("Move"), visible=True)
        move_button.connect("clicked", self.on_move_clicked)
        box.pack_start(move_button, False, False, 0)
        return box

    def _get_launch_config_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12, visible=True)

        if self.game.config:
            game_config = self.game.config.game_level.get("game", {})
        else:
            game_config = {}
        preferred_name = game_config.get("preferred_launch_config_name")

        if preferred_name:
            spacer = Gtk.Box()
            spacer.set_size_request(230, -1)
            box.pack_start(spacer, False, False, 0)

            if preferred_name == Game.PRIMARY_LAUNCH_CONFIG_NAME:
                text = _("The default launch option will be used for this game")
            else:
                text = _("The '%s' launch option will be used for this game") % preferred_name
            label = Gtk.Label(text)
            label.set_line_wrap(True)
            label.set_halign(Gtk.Align.START)
            label.set_xalign(0.0)
            label.set_valign(Gtk.Align.CENTER)
            box.pack_start(label, True, True, 0)
            button = Gtk.Button(_("Reset"))
            button.connect("clicked", self.on_reset_preferred_launch_config_clicked, box)
            button.set_valign(Gtk.Align.CENTER)
            box.pack_start(button, False, False, 0)
        else:
            box.hide()
        return box

    def on_reset_preferred_launch_config_clicked(self, _button, launch_config_box):
        game_config = self.game.config.game_level.get("game", {})
        game_config.pop("preferred_launch_config_name", None)
        game_config.pop("preferred_launch_config_index", None)
        launch_config_box.hide()

    def _get_runner_box(self):
        runner_box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)

        runner_label = Label(_("Runner"))
        runner_box.pack_start(runner_label, False, False, 0)

        self.runner_dropdown = self._get_runner_dropdown()
        runner_box.pack_start(self.runner_dropdown, True, True, 0)

        return runner_box

    def _get_banner_box(self):
        banner_box = Gtk.Grid()
        banner_box.set_margin_top(12)
        banner_box.set_column_spacing(12)
        banner_box.set_row_spacing(4)

        self._create_image_button(banner_box, "coverart_big", _("Set custom cover art"), _("Remove custom cover art"))
        self._create_image_button(banner_box, "banner", _("Set custom banner"), _("Remove custom banner"))
        self._create_image_button(banner_box, "icon", _("Set custom icon"), _("Remove custom icon"))

        return banner_box

    def _create_image_button(self, banner_box, image_type, image_tooltip, reset_tooltip):
        """This adds an image button and its reset button to the box given,
        and adds the image button to self.image_buttons for future reference."""

        image_button_container = Gtk.VBox()
        reset_button_container = Gtk.HBox()

        image_button = Gtk.Button()
        self._set_image(image_type, image_button)
        image_button.set_valign(Gtk.Align.CENTER)
        image_button.set_tooltip_text(image_tooltip)
        image_button.connect("clicked", self.on_custom_image_select, image_type)
        image_button_container.pack_start(image_button, True, True, 0)

        reset_button = Gtk.Button.new_from_icon_name("edit-undo-symbolic", Gtk.IconSize.MENU)
        reset_button.set_relief(Gtk.ReliefStyle.NONE)
        reset_button.set_tooltip_text(reset_tooltip)
        reset_button.connect("clicked", self.on_custom_image_reset_clicked, image_type)
        reset_button.set_valign(Gtk.Align.CENTER)
        reset_button_container.pack_start(reset_button, True, False, 0)

        banner_box.add(image_button_container)
        banner_box.attach_next_to(reset_button_container, image_button_container, Gtk.PositionType.BOTTOM, 1, 1)

        self.image_buttons[image_type] = image_button

    def _get_year_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)

        label = Label(_("Release year"))
        box.pack_start(label, False, False, 0)
        self.year_entry = NumberEntry()
        self.year_entry.set_max_length(10)
        if self.game:
            self.year_entry.set_text(str(self.game.year or ""))
        box.pack_start(self.year_entry, True, True, 0)

        return box

    def _get_playtime_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)

        label = Label(_("Playtime"))
        box.pack_start(label, False, False, 0)
        self.playtime_entry = Gtk.Entry()

        if self.game:
            self.playtime_entry.set_text(self.game.formatted_playtime)
        box.pack_start(self.playtime_entry, True, True, 0)

        return box

    def _set_image(self, image_format, image_button):
        scale_factor = self.get_scale_factor()
        service_media = self.service_medias[image_format]
        game_slug = self.slug or (self.game.slug if self.game else "")
        media_path = resolve_media_path(service_media.get_possible_media_paths(game_slug))
        try:
            image = ScaledImage.new_from_media_path(media_path, service_media.config_ui_size, scale_factor)
            image_button.set_image(image)
        except Exception as ex:
            # We need to survive nasty data in the media files, so the user can replace
            # them.
            logger.exception("Unable to load media '%s': %s", image_format, ex)

    def _get_runner_dropdown(self):
        runner_liststore = self._get_runner_liststore()
        runner_dropdown = Gtk.ComboBox.new_with_model(runner_liststore)
        runner_dropdown.set_id_column(1)
        runner_index = 0
        if self.runner_name:
            for runner in runner_liststore:
                if self.runner_name == str(runner[1]):
                    break
                runner_index += 1
        self.runner_index = runner_index
        runner_dropdown.set_active(self.runner_index)
        runner_dropdown.connect("changed", self.on_runner_changed)
        cell = Gtk.CellRendererText()
        cell.props.ellipsize = Pango.EllipsizeMode.END
        runner_dropdown.pack_start(cell, True)
        runner_dropdown.add_attribute(cell, "text", 0)
        return runner_dropdown

    @staticmethod
    def _get_runner_liststore():
        """Build a ListStore with available runners."""
        runner_liststore = Gtk.ListStore(str, str)
        runner_liststore.append((_("Select a runner from the list"), ""))
        for runner in runners.get_installed():
            description = runner.description
            runner_liststore.append(("%s (%s)" % (runner.human_name, description), runner.name))
        return runner_liststore

    def on_slug_change_clicked(self, widget):
        if self.slug_entry.get_sensitive() is False:
            widget.set_label(_("Apply"))
            self.slug_entry.set_sensitive(True)
        else:
            self.change_game_slug()

    def on_slug_entry_activate(self, _widget):
        self.change_game_slug()

    def change_game_slug(self):
        slug = self.slug_entry.get_text()
        self.slug = slug
        self.slug_entry.set_sensitive(False)
        self.slug_change_button.set_label(_("Change"))
        AsyncCall(download_lutris_media, self.refresh_all_images_cb, self.slug)

    def refresh_all_images_cb(self, _result, _error):
        for image_type, image_button in self.image_buttons.items():
            self._set_image(image_type, image_button)

    def on_move_clicked(self, _button):
        new_location = DirectoryDialog(
            "Select new location for the game", default_path=self.game.directory, parent=self
        )
        if not new_location.folder or new_location.folder == self.game.directory:
            return
        move_dialog = MoveDialog(self.game, new_location.folder, parent=self)
        move_dialog.connect("game-moved", self.on_game_moved)
        move_dialog.move()

    def on_game_moved(self, dialog):
        """Show a notification when the game is moved"""
        new_directory = dialog.new_directory
        if new_directory:
            self.game = Game(self.game.id)
            self.lutris_config = self.game.config
            self._rebuild_tabs()
            self.directory_entry.set_text(new_directory)
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
            self.update_advanced_switch_visibilty(self.notebook.get_current_page())

    def on_search_entry_changed(self, entry):
        """Callback for the search input keypresses"""
        text = entry.get_text().lower().strip()
        self._set_filter(text)

    def on_show_advanced_options_toggled(self, is_active):
        settings.write_setting("show_advanced_options", is_active)

        self._set_advanced_options_visible(is_active)

    def _set_advanced_options_visible(self, value):
        """Change visibility of advanced options across all config tabs."""
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
        if self.runner_index and new_runner_index != self.runner_index:
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
                self.runner_index = new_runner_index
                self._switch_runner(widget)
            else:
                # Revert the dropdown menu to the previously selected runner
                widget.set_active(self.runner_index)
        else:
            self.runner_index = new_runner_index
            self._switch_runner(widget)

    def _switch_runner(self, widget):
        """Rebuilds the UI on runner change"""
        current_page = self.notebook.get_current_page()
        if self.runner_index == 0:
            logger.info("No runner selected, resetting configuration")
            self.runner_name = None
            self.lutris_config = None
        else:
            runner_name = widget.get_model()[self.runner_index][1]
            if runner_name == self.runner_name:
                logger.debug("Runner unchanged, not creating a new config")
                return
            logger.info("Creating new configuration with runner %s", runner_name)
            self.runner_name = runner_name
            self.lutris_config = LutrisConfig(runner_slug=self.runner_name, level="game")
        self._rebuild_tabs()
        self.runner_warning_box.update_warning(self.runner_name)
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

    def is_valid(self):
        if not self.runner_name:
            ErrorDialog(_("Runner not provided"), parent=self)
            return False
        if not self.name_entry.get_text():
            ErrorDialog(_("Please fill in the name"), parent=self)
            return False
        if self.runner_name == "steam" and not self.lutris_config.game_config.get("appid"):
            ErrorDialog(_("Steam AppID not provided"), parent=self)
            return False
        playtime_text = self.playtime_entry.get_text()
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
        name = self.name_entry.get_text()
        sortname = self.sortname_entry.get_text()

        if not self.slug:
            self.slug = slugify(name)
        if self.slug != self.initial_slug:
            AsyncCall(download_lutris_media, None, self.slug)
        if not self.game:
            self.game = Game()

        year = None
        if self.year_entry.get_text():
            year = int(self.year_entry.get_text())

        playtime = None
        playtime_text = self.playtime_entry.get_text()
        if playtime_text and playtime_text != self.game.formatted_playtime:
            playtime = parse_playtime(playtime_text)

        if not self.lutris_config.game_config_id:
            self.lutris_config.game_config_id = make_game_config_id(self.slug)

        self.game.name = name
        self.game.sortname = sortname
        self.game.slug = self.slug
        self.game.year = year
        if playtime:
            self.game.playtime = playtime
        self.game.is_installed = True
        self.game.config = self.lutris_config
        self.game.runner_name = self.runner_name

        if "icon" not in self.game.custom_images:
            self.game.runner.extract_icon(self.slug)

        self.game.save()
        self.destroy()
        self.saved = True
        return True

    def on_custom_image_select(self, _widget, image_type):
        dialog = Gtk.FileChooserNative.new(
            _("Please choose a custom image"),
            self,
            Gtk.FileChooserAction.OPEN,
            None,
            None,
        )

        image_filter = Gtk.FileFilter()
        image_filter.set_name(_("Images"))
        image_filter.add_pixbuf_formats()
        dialog.add_filter(image_filter)
        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            image_path = dialog.get_filename()
            self.save_custom_media(image_type, image_path)
        dialog.destroy()

    def on_custom_image_reset_clicked(self, _widget, image_type):
        self.refresh_image(image_type)

    def save_custom_media(self, image_type: str, image_path: str) -> None:
        slug = self.slug or self.game.slug
        service_media = self.service_medias[image_type]
        self.game.custom_images.add(image_type)
        dest_paths = service_media.get_possible_media_paths(slug)

        if image_path not in dest_paths:
            ext = get_image_file_extension(image_path)

            if ext:
                for candidate in dest_paths:
                    if candidate.casefold().endswith(ext):
                        self._save_copied_media_to(candidate, image_type, image_path)
                        return

            self._save_transcoded_media_to(dest_paths[0], image_type, image_path)

    def _save_copied_media_to(self, dest_path: str, image_type: str, image_path: str) -> None:
        """Copies a media file to the dest_path, but trashes the existing media
        for the game first. When complete, this updates the button indicated by
        image_type as well."""
        slug = self.slug or self.game.slug
        service_media = self.service_medias[image_type]

        def on_trashed():
            AsyncCall(copy_image, self.image_refreshed_cb)

        def copy_image():
            shutil.copy(image_path, dest_path, follow_symlinks=True)
            MEDIA_CACHE_INVALIDATED.fire()
            return image_type

        service_media.trash_media(slug, completion_function=on_trashed)

    def _save_transcoded_media_to(self, dest_path: str, image_type: str, image_path: str) -> None:
        """Transcode an image, copying it to a new path and selecting the file type
        based on the file extension of dest_path. Trashes all media for the current
        game too. Runs in the background, and when complete updates the button indicated
        by image_type."""
        slug = self.slug or self.game.slug
        service_media = self.service_medias[image_type]
        ext = get_image_file_extension(dest_path) or ".png"
        file_format = {".jpg": "jpeg", ".png": "png"}[ext]

        # If we must transcode the image, we'll scale the image up based on
        # the UI scale factor, to try to avoid blurriness. Of course this won't
        # work if the user changes the scaling later, but what can you do.
        scale_factor = self.get_scale_factor()
        width, height = service_media.custom_media_storage_size
        width = width * scale_factor
        height = height * scale_factor
        temp_file = dest_path + ".tmp"

        def transcode():
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(image_path, width, height)
            # JPEG encoding looks rather better at high quality;
            # PNG encoding just ignores this option.
            pixbuf.savev(temp_file, file_format, ["quality"], ["100"])
            service_media.trash_media(slug, completion_function=on_trashed)

        def transcode_cb(_result, error):
            if error:
                raise error

        def on_trashed():
            os.rename(temp_file, dest_path)
            MEDIA_CACHE_INVALIDATED.fire()
            self.image_refreshed_cb(image_type)

        AsyncCall(transcode, transcode_cb)

    def refresh_image(self, image_type):
        slug = self.slug or self.game.slug
        service_media = self.service_medias[image_type]
        self.game.custom_images.discard(image_type)

        def on_trashed():
            AsyncCall(download, self.image_refreshed_cb)

        def download():
            download_lutris_media(slug)
            return image_type

        service_media.trash_media(slug, completion_function=on_trashed)

    def refresh_image_cb(self, image_type, error):
        return image_type

    def image_refreshed_cb(self, image_type, _error=None):
        if image_type:
            self._set_image(image_type, self.image_buttons[image_type])
            service_media = self.service_medias[image_type]
            service_media.run_system_update_desktop_icons()


class RunnerMessageBox(UnderslungMessageBox):
    def __init__(self):
        super().__init__(margin_left=12, margin_right=12, icon_name="dialog-warning")

    def update_warning(self, runner_name):
        try:
            if runner_name:
                runner_class = import_runner(runner_name)
                runner = runner_class()
                warning = runner.runner_warning
                if warning:
                    self.show_markup(warning)
                    return
            self.show_markup(None)
        except Exception as ex:
            self.show_message(gtk_safe(ex))
