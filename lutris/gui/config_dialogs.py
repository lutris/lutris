import os
from gi.repository import Gtk, Pango

from lutris import runners, settings
from lutris.config import LutrisConfig, TEMP_CONFIG, make_game_config_id
from lutris.game import Game
from lutris import gui
from lutris.gui.config_boxes import GameBox, RunnerBox, SystemBox
from lutris.gui.dialogs import ErrorDialog
from lutris.gui.widgets import VBox, Dialog
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.util import datapath
from lutris.gui.widgets import get_pixbuf_for_game, get_pixbuf, BANNER_SIZE, ICON_SIZE

DIALOG_WIDTH = 550
DIALOG_HEIGHT = 550


class SlugEntry(Gtk.Entry, Gtk.Editable):
    def __init__(self):
        super(SlugEntry, self).__init__()

    def do_insert_text(self, new_text, length, position):
        """Filter inserted characters to only accept alphanumeric and dashes"""
        new_text = ''.join([c for c in new_text if c.isalnum() or c == '-']).lower()
        if new_text:
            self.get_buffer().insert_text(position, new_text, length)
            return position + length
        return position


class NumberEntry(Gtk.Entry, Gtk.Editable):
    def __init__(self):
        super(NumberEntry, self).__init__()

    def do_insert_text(self, new_text, length, position):
        """Filter inserted characters to only accept numbers"""
        new_text = ''.join([c for c in new_text if c.isnumeric()])
        if new_text:
            self.get_buffer().insert_text(position, new_text, length)
            return position + length
        return position


class GameDialogCommon(object):
    no_runner_label = "Select a runner in the Game Info tab"

    @staticmethod
    def build_scrolled_window(widget):
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(widget)
        return scrolled_window

    def build_notebook(self):
        self.notebook = Gtk.Notebook()
        self.vbox.pack_start(self.notebook, True, True, 10)

    def build_tabs(self, config_level):
        if config_level == 'game':
            self._build_info_tab()
            self._build_game_tab()
        self._build_runner_tab(config_level)
        self._build_system_tab(config_level)

    def _build_info_tab(self):
        info_box = VBox()

        info_box.pack_start(self._get_name_box(), False, False, 5)  # Game name

        if self.game:
            info_box.pack_start(self._get_slug_box(), False, False, 5)  # Game id
            info_box.pack_start(self._get_banner_box(), False, False, 5)  # Banner

        self.runner_box = self._get_runner_box()
        info_box.pack_start(self.runner_box, False, False, 5)  # Runner

        info_box.pack_start(self._get_platform_box(), False, False, 5)
        info_box.pack_start(self._get_year_box(), False, False, 5)

        info_sw = self.build_scrolled_window(info_box)
        self._add_notebook_tab(info_sw, "Game info")

    def _get_name_box(self):
        box = Gtk.HBox()

        label = Gtk.Label(label="Name")
        box.pack_start(label, False, False, 20)

        self.name_entry = Gtk.Entry()
        if self.game:
            self.name_entry.set_text(self.game.name)
        box.pack_start(self.name_entry, True, True, 20)

        return box

    def _get_slug_box(self):
        box = Gtk.HBox()

        label = Gtk.Label(label="Identifier")
        box.pack_start(label, False, False, 20)

        self.slug_entry = SlugEntry()
        self.slug_entry.set_text(self.game.slug)
        self.slug_entry.set_sensitive(False)
        self.slug_entry.connect('activate', self.on_slug_entry_activate)
        box.pack_start(self.slug_entry, True, True, 0)

        slug_change_button = Gtk.Button("Change")
        slug_change_button.connect('clicked', self.on_slug_change_clicked)
        box.pack_start(slug_change_button, False, False, 20)

        return box

    def _get_runner_box(self):
        runner_box = Gtk.HBox()
        runner_label = Gtk.Label("Runner")
        runner_label.set_alignment(0.5, 0.5)
        self.runner_dropdown = self._get_runner_dropdown()
        install_runners_btn = Gtk.Button(label="Install runners")
        install_runners_btn.connect('clicked', self.on_install_runners_clicked)
        install_runners_btn.set_margin_right(20)

        runner_box.pack_start(runner_label, False, False, 20)
        runner_box.pack_start(self.runner_dropdown, False, False, 20)
        runner_box.pack_start(install_runners_btn, False, False, 0)
        return runner_box

    def _get_banner_box(self):
        banner_box = Gtk.HBox()
        banner_label = Gtk.Label("Banner")
        banner_label.set_alignment(0.5, 0.5)
        self.banner_button = Gtk.Button()
        self._set_image('banner')
        self.banner_button.connect('clicked', self.on_custom_image_select, 'banner')

        reset_banner_button = Gtk.Button.new_from_icon_name('edit-clear',
                                                            Gtk.IconSize.MENU)
        reset_banner_button.set_relief(Gtk.ReliefStyle.NONE)
        reset_banner_button.set_tooltip_text("Remove custom banner")
        reset_banner_button.connect('clicked',
                                    self.on_custom_image_reset_clicked,
                                    'banner')

        self.icon_button = Gtk.Button()
        self._set_image('icon')
        self.icon_button.connect('clicked', self.on_custom_image_select, 'icon')

        reset_icon_button = Gtk.Button.new_from_icon_name('edit-clear',
                                                          Gtk.IconSize.MENU)
        reset_icon_button.set_relief(Gtk.ReliefStyle.NONE)
        reset_icon_button.set_tooltip_text("Remove custom icon")
        reset_icon_button.connect('clicked', self.on_custom_image_reset_clicked, 'icon')

        banner_box.pack_start(banner_label, False, False, 20)
        banner_box.pack_start(self.banner_button, False, False, 0)
        banner_box.pack_start(reset_banner_button, False, False, 0)
        banner_box.pack_start(self.icon_button, False, False, 0)
        banner_box.pack_start(reset_icon_button, False, False, 0)
        return banner_box

    def _get_platform_box(self):
        box = Gtk.HBox()

        label = Gtk.Label(label="Platform")
        box.pack_start(label, False, False, 20)

        self.platform_entry = Gtk.Entry()
        if self.game:
            self.platform_entry.set_text(self.game.platform)
            if self.game.runner:
                self.platform_entry.set_placeholder_text(self.game.runner.platform)
        box.pack_start(self.platform_entry, True, True, 20)

        return box

    def _get_year_box(self):
        box = Gtk.HBox()

        label = Gtk.Label(label="Release year")
        box.pack_start(label, False, False, 20)

        self.year_entry = NumberEntry()
        if self.game:
            self.year_entry.set_text(str(self.game.year or ''))
        box.pack_start(self.year_entry, True, True, 20)

        return box

    def _set_image(self, image_format):
        assert image_format in ('banner', 'icon')
        image = Gtk.Image()
        game_slug = self.game.slug if self.game else ''
        image.set_from_pixbuf(get_pixbuf_for_game(game_slug, image_format))
        if image_format == 'banner':
            self.banner_button.set_image(image)
        else:
            self.icon_button.set_image(image)

    def _set_icon_image(self):
        image = Gtk.Image()
        game_slug = self.game.slug if self.game else ''
        image.set_from_pixbuf(get_pixbuf_for_game(game_slug, 'banner'))
        self.banner_button.set_image(image)

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
        runner_dropdown.set_active(runner_index)
        runner_dropdown.connect("changed", self.on_runner_changed)
        cell = Gtk.CellRendererText()
        cell.props.ellipsize = Pango.EllipsizeMode.END
        runner_dropdown.pack_start(cell, True)
        runner_dropdown.add_attribute(cell, 'text', 0)
        return runner_dropdown

    @staticmethod
    def _get_runner_liststore():
        """Build a ListStore with available runners."""
        runner_liststore = Gtk.ListStore(str, str)
        runner_liststore.append(("Select a runner from the list", ""))
        for runner in runners.get_installed():
            description = runner.description
            runner_liststore.append(
                ("%s (%s)" % (runner.human_name, description), runner.name)
            )
        return runner_liststore

    def on_slug_change_clicked(self, widget):
        if self.slug_entry.get_sensitive() is False:
            self.slug_entry.set_sensitive(True)
        else:
            self.change_game_slug()

    def on_slug_entry_activate(self, widget):
        self.change_game_slug()

    def change_game_slug(self):
        self.slug = self.slug_entry.get_text()
        self.slug_entry.set_sensitive(False)

    def on_install_runners_clicked(self, _button):
        runners_dialog = gui.runnersdialog.RunnersDialog()
        runners_dialog.connect("runner-installed",
                               self._update_runner_dropdown)

    def _update_runner_dropdown(self, _widget):
        active_id = self.runner_dropdown.get_active_id()
        self.runner_dropdown.set_model(self._get_runner_liststore())
        self.runner_dropdown.set_active_id(active_id)

    def _build_game_tab(self):
        if self.game and self.runner_name:
            self.game.runner_name = self.runner_name
            try:
                self.game.runner = runners.import_runner(self.runner_name)
            except runners.InvalidRunner:
                pass
            self.game_box = GameBox(self.lutris_config, self.game)
            game_sw = self.build_scrolled_window(self.game_box)
        elif self.runner_name:
            game = Game(None)
            game.runner_name = self.runner_name
            self.game_box = GameBox(self.lutris_config, game)
            game_sw = self.build_scrolled_window(self.game_box)
        else:
            game_sw = Gtk.Label(label=self.no_runner_label)
            self.game.runner = None
        self._add_notebook_tab(game_sw, "Game options")

    def _build_runner_tab(self, config_level):
        if self.runner_name:
            self.runner_box = RunnerBox(self.lutris_config)
            runner_sw = self.build_scrolled_window(self.runner_box)
        else:
            runner_sw = Gtk.Label(label=self.no_runner_label)
        self._add_notebook_tab(runner_sw, "Runner options")

    def _build_system_tab(self, config_level):
        self.system_box = SystemBox(self.lutris_config)
        self.system_sw = self.build_scrolled_window(self.system_box)
        self._add_notebook_tab(self.system_sw, "System options")

    def _add_notebook_tab(self, widget, label):
        self.notebook.append_page(widget, Gtk.Label(label=label))

    def build_action_area(self, button_callback, callback2=None):
        self.action_area.set_layout(Gtk.ButtonBoxStyle.EDGE)

        # Advanced settings checkbox
        checkbox = Gtk.CheckButton(label="Show advanced options")
        value = settings.read_setting('show_advanced_options')
        if value == 'True':
            checkbox.set_active(value)
        checkbox.connect("toggled", self.on_show_advanced_options_toggled)
        self.action_area.pack_start(checkbox, False, False, 5)

        # Buttons
        hbox = Gtk.HBox()
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", self.on_cancel_clicked)
        hbox.pack_start(cancel_button, True, True, 10)

        save_button = Gtk.Button(label="Save")
        if callback2:
            save_button.connect("clicked", button_callback, callback2)
        else:
            save_button.connect("clicked", button_callback)
        hbox.pack_start(save_button, True, True, 0)
        self.action_area.pack_start(hbox, True, True, 0)

    def on_show_advanced_options_toggled(self, checkbox):
        value = True if checkbox.get_active() else False
        settings.write_setting('show_advanced_options', value)

        self._set_advanced_options_visible(value)

    def _set_advanced_options_visible(self, value):
        """Change visibility of advanced options across all config tabs."""
        widgets = self.system_box.get_children()
        if self.runner_name:
            widgets += self.runner_box.get_children()
        if self.game:
            widgets += self.game_box.get_children()

        for widget in widgets:
            if widget.get_style_context().has_class('advanced'):
                widget.set_visible(value)
                if value:
                    widget.set_no_show_all(not value)
                    widget.show_all()

    def on_runner_changed(self, widget):
        """Action called when runner drop down is changed."""
        runner_index = widget.get_active()
        current_page = self.notebook.get_current_page()

        if runner_index == 0:
            self.runner_name = None
            self.lutris_config = LutrisConfig()
        else:
            self.runner_name = widget.get_model()[runner_index][1]
            self.lutris_config = LutrisConfig(
                runner_slug=self.runner_name,
                game_config_id=self.game_config_id,
                level='game'
            )

        self._rebuild_tabs()
        self.notebook.set_current_page(current_page)
        if self.game.runner:
            self.platform_entry.set_placeholder_text(self.game.runner.platform)
        else:
            self.platform_entry.set_placeholder_text('')

    def _rebuild_tabs(self):
        for i in range(self.notebook.get_n_pages(), 1, -1):
            self.notebook.remove_page(i - 1)
        self._build_game_tab()
        self._build_runner_tab('game')
        self._build_system_tab('game')
        self.show_all()

    def on_cancel_clicked(self, widget=None):
        """Dialog destroy callback."""
        self.destroy()

    def is_valid(self):
        name = self.name_entry.get_text()
        if not self.runner_name:
            ErrorDialog("Runner not provided")
            return False
        if not name:
            ErrorDialog("Please fill in the name")
            return False
        return True

    def on_save(self, _button, callback=None):
        """Save game info and destroy widget. Return True if success."""
        if not self.is_valid():
            return False
        name = self.name_entry.get_text()

        if not self.slug:
            self.slug = slugify(name)

        if not self.game:
            self.game = Game()

        platform = self.platform_entry.get_text()

        year = None
        if self.year_entry.get_text():
            year = int(self.year_entry.get_text())

        if self.lutris_config.game_config_id == TEMP_CONFIG:
            self.lutris_config.game_config_id = self.get_config_id()

        runner_class = runners.import_runner(self.runner_name)
        runner = runner_class(self.lutris_config)
        self.game.name = name
        self.game.slug = self.slug
        self.game.platform = platform
        self.game.year = year
        self.game.runner_name = self.runner_name
        self.game.config = self.lutris_config
        self.game.directory = runner.game_path
        self.game.is_installed = True
        if self.runner_name in ('steam', 'winesteam'):
            self.game.steamid = self.lutris_config.game_config['appid']
        self.game.save()
        self.destroy()
        logger.debug("Saved %s", name)
        self.saved = True
        if callback:
            callback()

    def on_custom_image_select(self, widget, image_type):
        dialog = Gtk.FileChooserDialog("Please choose a custom image", self,
                                       Gtk.FileChooserAction.OPEN,
                                       (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

        image_filter = Gtk.FileFilter()
        image_filter.set_name("Images")
        image_filter.add_pixbuf_formats()
        dialog.add_filter(image_filter)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            image_path = dialog.get_filename()
            if image_type == 'banner':
                self.game.has_custom_banner = True
                dest_path = datapath.get_banner_path(self.game.slug)
                size = BANNER_SIZE
                file_format = 'jpeg'
            else:
                self.game.has_custom_icon = True
                dest_path = datapath.get_icon_path(self.game.slug)
                size = ICON_SIZE
                file_format = 'png'
            pixbuf = get_pixbuf(image_path, None, size)
            pixbuf.savev(dest_path, file_format, [], [])
            self._set_image(image_type)

        dialog.destroy()

    def on_custom_image_reset_clicked(self, widget, image_type):
        if image_type == 'banner':
            self.game.has_custom_banner = False
            dest_path = datapath.get_banner_path(self.game.slug)
        elif image_type == 'icon':
            self.game.has_custom_icon = False
            dest_path = datapath.get_icon_path(self.game.slug)
        else:
            raise ValueError('Unsupported image type %s', image_type)
        os.remove(dest_path)
        self._set_image(image_type)


class AddGameDialog(Dialog, GameDialogCommon):
    """Add game dialog class."""
    def __init__(self, parent, game=None, runner=None, callback=None):
        super(AddGameDialog, self).__init__("Add a new game", parent=parent)
        self.game = game
        self.saved = False

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)
        if game:
            self.runner_name = game.runner_name
            self.slug = game.slug
        else:
            self.runner_name = runner
            self.slug = None

        self.game_config_id = self.get_config_id()
        self.lutris_config = LutrisConfig(runner_slug=self.runner_name,
                                          game_config_id=self.game_config_id,
                                          level='game')
        self.build_notebook()
        self.build_tabs('game')
        self.build_action_area(self.on_save, callback)
        self.name_entry.grab_focus()
        self.show_all()

    def get_config_id(self):
        """For new games, create a special config type that won't be read
        from disk.
        """
        return make_game_config_id(self.slug) if self.slug else TEMP_CONFIG


class EditGameConfigDialog(Dialog, GameDialogCommon):
    """Game config edit dialog."""
    def __init__(self, parent, game, callback):
        super(EditGameConfigDialog, self).__init__(
            "Configure %s" % game.name,
            parent=parent
        )
        self.game = game
        self.lutris_config = game.config
        self.game_config_id = game.config.game_config_id
        self.slug = game.slug
        self.runner_name = game.runner_name

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)

        self.build_notebook()
        self.build_tabs('game')
        self.build_action_area(self.on_save, callback)
        self.show_all()


class RunnerConfigDialog(Dialog, GameDialogCommon):
    """Runner config edit dialog."""
    def __init__(self, runner, parent=None):
        self.runner_name = runner.__class__.__name__
        super(RunnerConfigDialog, self).__init__(
            "Configure %s" % runner.human_name,
            parent=parent
        )

        self.game = None
        self.saved = False
        self.lutris_config = LutrisConfig(runner_slug=self.runner_name)

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)

        self.build_notebook()
        self.build_tabs('runner')
        self.build_action_area(self.on_save)
        self.show_all()

    def on_save(self, wigdet, data=None):
        self.lutris_config.save()
        self.destroy()


class SystemConfigDialog(Dialog, GameDialogCommon):
    def __init__(self, parent=None):
        super(SystemConfigDialog, self).__init__("System preferences", parent=parent)

        self.game = None
        self.runner_name = None
        self.lutris_config = LutrisConfig()

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)

        self.system_box = SystemBox(self.lutris_config)
        self.system_sw = self.build_scrolled_window(self.system_box)
        self.vbox.pack_start(self.system_sw, True, True, 0)
        self.build_action_area(self.on_save)
        self.show_all()

    def on_save(self, widget):
        self.lutris_config.save()
        self.destroy()
