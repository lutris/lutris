"""Configuration dialogs"""
import os
import glob

from gi.repository import Gtk, Pango, GObject, GdkPixbuf
from gi.repository.GdkPixbuf import Pixbuf

from lutris import runners, settings
from lutris.config import LutrisConfig, TEMP_CONFIG, make_game_config_id
from lutris.game import Game
from lutris import gui
from lutris.gui.cellrenderers import GridViewCellRendererText
from lutris.gui.config_boxes import GameBox,  RunnerBox, SystemBox
from lutris.gui.dialogs import ErrorDialog
from lutris.gui.widgets import VBox, Dialog
from lutris.util.log import logger
from lutris.util.strings import slugify

DIALOG_WIDTH = 610
DIALOG_HEIGHT = 550

#Padding values:            v{Window  v{Notebook v{Bannersw    v{2 banners/row
IMAGE_WIDTH = (DIALOG_WIDTH - 20      - 40       - 50)         / 2

IMAGE_HEIGHT = IMAGE_WIDTH * 108 / 230 


class GameDialogCommon(object):
    no_runner_label = "Select a runner in the Game Info tab"

    @staticmethod
    def build_scrolled_window(widget):
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add_with_viewport(widget)
        return scrolled_window

    def build_notebook(self):
        self.notebook = Gtk.Notebook()
        self.vbox.pack_start(self.notebook, True, True, 10)

    def build_tabs(self, config_level):
        if config_level == 'game':
            self._build_info_tab()
            self._build_game_tab()
            
            if self.game is not None:
                self._build_art_tab()

        self._build_runner_tab(config_level)
        self._build_system_tab(config_level)

    def _build_info_tab(self):
        info_box = VBox()

        # Game name
        self.name_entry = Gtk.Entry()
        if self.game is not None:
            self.name_entry.set_text(self.game.name)
        name_box = self._build_entry_box(self.name_entry, "Name     ")
        info_box.pack_start(name_box, False, False, 5)

        # Game slug
        if self.game is not None:
            self.slug_entry = Gtk.Entry()
            self.slug_entry.set_text(self.game.slug)
            self.slug_entry.set_sensitive(False)
            slug_box = self._build_entry_box(self.slug_entry, "Identifier")
            info_box.pack_start(slug_box, False, False, 5)

        # Runner
        self.runner_box = self._get_runner_box()
        info_box.pack_start(self.runner_box, False, False, 5)

        info_sw = self.build_scrolled_window(info_box)
        self._add_notebook_tab(info_sw, "Game info")

    def _build_art_tab(self):
        # Art box: main container of the notebook page
        self.art_box = Gtk.Grid(column_homogeneous=True)
        self.art_box.set_hexpand(True)
        self.art_box.set_halign(Gtk.Align.FILL)

        # Label
        label = Gtk.Label("Banner")
        label.set_alignment(0, 0.5)
        label.set_margin_left(10)
        self.art_box.attach(label, 0, 1, 4, 1)

        # Iconview of the banners
        self.bannerstore = Gtk.ListStore(Pixbuf, str)
        self.bannerview = Gtk.IconView()
        self.bannerview.set_item_orientation(Gtk.Orientation.VERTICAL)
        self.bannerview.set_model(self.bannerstore)
        self.bannerview.set_pixbuf_column(0)
        self.bannerview.set_hexpand(True)
        self.bannerview.set_halign(Gtk.Align.FILL)
        self.bannerview.set_pixbuf_column(0)
        self.bannerview.connect('selection-changed', self.on_banner_selected)

        # Banner ScrolledWindow : a scrollable window around iconview
        self.banner_sw = Gtk.ScrolledWindow.new()
        self.banner_sw.set_hexpand(True)
        self.banner_sw.set_halign(Gtk.Align.FILL)
        self.banner_sw.set_size_request(DIALOG_WIDTH - 70, DIALOG_HEIGHT/3)
        self.banner_sw.add(self.bannerview) 

        # Banner_frame: a frame around banner scrollwindow
        self.banner_frame = Gtk.Frame()
        self.banner_frame.set_hexpand(True)
        self.banner_frame.set_halign(Gtk.Align.FILL)
        self.banner_frame.add(self.banner_sw)
        self.banner_frame.set_margin_bottom(10)
        self.art_box.attach(self.banner_frame, 0,0,16,1)        

        # Banner folder button: selects which folder to display
        self.banner_folder_btn = Gtk.FileChooserButton()     
        self.banner_folder_btn.set_action(Gtk.FileChooserAction(2)) #Equivalent to SELECT_FOLDER
        self.banner_folder_btn.set_margin_right(20)
        
        #self.banner_folder_btn.connect('update-preview', self.on_banner_folder_changed)
        #self.banner_folder_btn.connect('current-folder-changed', self.on_banner_folder_changed)
        self.banner_folder_btn.connect('selection-changed', self.on_banner_folder_changed)
        #self.banner_folder_btn.connect('file-set', self.on_banner_folder_changed)

        self.banner_default_btn = Gtk.Button(label="Default")
        self.banner_default_btn.set_margin_left(20)
        self.banner_default_btn.connect('clicked', self.on_banner_default_clicked)
        self.art_box.attach(self.banner_default_btn, 12, 1, 4, 1)
        
        if self.banner_folder is not None:
            self.banner_folder_btn.set_filename(self.banner_folder) # Runs _fill_banerstore automatically
        else:
            self.banner_folder_btn.set_filename(os.path.join(settings.BANNER_PATH, self.game.slug))
        self.art_box.attach(self.banner_folder_btn, 2, 1, 11, 1)

        # Update tab
        self.art_sw = self.build_scrolled_window(self.art_box)
        self.art_sw.set_border_width(20)
        self._add_notebook_tab(self.art_sw, "Artwork")

    def on_banner_default_clicked(self,*args):
        self.banner_folder_btn.set_filename(
            os.path.join(settings.BANNER_PATH, self.game.slug)
            )

        self.game.banner = None

    
            
    def _fill_bannerstore(self):
        for row in self.bannerstore:
            self.bannerstore.remove(row.iter)

        #this matches every png & jpg & makes sure default.*g is the first banner displayed
        try:
            file_list = glob.glob(os.path.join(self.banner_folder, "*.*g"))
            file_list.remove(glob.glob(os.path.join(self.banner_folder, "default.*g"))[0])
            file_list = glob.glob(os.path.join(self.banner_folder, "default.*g")) + file_list
        except IndexError:
            file_list = glob.glob(os.path.join(self.banner_folder, "*.*g"))

        for filename in file_list: 
            pixbuf = Pixbuf.new_from_file_at_size(filename, IMAGE_WIDTH, IMAGE_HEIGHT)
            self.bannerstore.append([pixbuf, filename])
    
    def on_banner_folder_changed(self, folder_button):
        self.banner_folder = folder_button.get_filename()
        if self.banner_folder is not None:
            self._fill_bannerstore()

    def on_banner_selected(self, bannerview):
        try:
            self.banner_path = self.bannerstore[ bannerview.get_selected_items()[0] ][1]
        except IndexError:
            pass
        
    def _build_entry_box(self, entry, label_text=None):
        box = Gtk.HBox()
        if label_text:
            label = Gtk.Label(label=label_text)
            box.pack_start(label, False, False, 20)
        box.pack_start(entry, True, True, 20)
        return box

    

    def _get_runner_box(self):
        runner_box = Gtk.HBox()
        label = Gtk.Label("Runner   ")
        label.set_alignment(0.5, 0.5)
        self.runner_dropdown = self._get_runner_dropdown()
        install_runners_btn = Gtk.Button(label="Install runners")
        install_runners_btn.connect('clicked', self.on_install_runners_clicked)
        install_runners_btn.set_margin_right(20)

        runner_box.pack_start(label, False, False, 20)
        runner_box.pack_start(self.runner_dropdown, False, False, 20)
        runner_box.pack_start(install_runners_btn, False, False, 0)
        return runner_box

    def _get_runner_dropdown(self):
        runner_liststore = self._get_runner_liststore()
        runner_dropdown = Gtk.ComboBox.new_with_model(runner_liststore)
        runner_dropdown.set_id_column(1)
        runner_index = 0
        if self.game is not None:
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
                ("%s (%s)" % (runner.name, description), runner.name)
            )
        return runner_liststore

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

    def build_action_area(self, label, button_callback, callback2=None):
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

        button = Gtk.Button(label=label)
        if callback2:
            button.connect("clicked", button_callback, callback2)
        else:
            button.connect("clicked", button_callback)
        hbox.pack_start(button, True, True, 0)
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
        if self.game is not None:
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

        # Do not modify slug
        if not self.slug:
            self.slug = slugify(name)

        if not self.game:
            self.game = Game()

        if self.lutris_config.game_config_id == TEMP_CONFIG:
            self.lutris_config.game_config_id = self.get_config_id()

        runner_class = runners.import_runner(self.runner_name)
        runner = runner_class(self.lutris_config)
        self.game.name = name
        self.game.slug = self.slug
        self.game.runner_name = self.runner_name
        self.game.config = self.lutris_config
        self.game.directory = runner.game_path
        self.game.is_installed = True
        self.game.banner = self.banner_path if self.banner_path else None
        self.game.icon = self.icon_path if self.icon_path else None

        if self.runner_name in ('steam', 'winesteam'):
            self.game.steamid = self.lutris_config.game_config['appid']
        self.game.save()
        self.destroy()
        logger.debug("Saved %s", name)
        self.saved = True
        if callback:
            callback()


class AddGameDialog(Dialog, GameDialogCommon):
    """Add game dialog class."""
    def __init__(self, parent, game=None, callback=None):
        super(AddGameDialog, self).__init__("Add a new game", parent=parent)
        self.game = game
        self.saved = False

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)
        if game is not None:
            self.runner_name = game.runner_name
            self.slug = game.slug
            self.banner_path = self.game.banner
            self.banner_folder = os.path.dirname(self.banner_path) \
                                    if self.banner_path is not None \
                                    else None
            self.icon_path = self.game.icon
            self.icon_folder = os.path.dirname(self.icon_path) \
                                    if self.icon_path is not None \
                                    else None
        else:
            self.runner_name = None
            self.slug = None

        self.game_config_id = self.get_config_id()
        self.lutris_config = LutrisConfig(runner_slug=self.runner_name,
                                          game_config_id=self.game_config_id,
                                          level='game')
        self.build_notebook()
        self.build_tabs('game')
        self.build_action_area("Add", self.on_save, callback)
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
            "Configure %s" % game.name, parent
        )
        self.game = game

        # Banner path is the actual path to the banner
        self.banner_path = self.game.banner
        self.banner_folder = os.path.dirname(self.banner_path) \
                                if self.banner_path is not None \
                                else None
        self.icon_path = self.game.icon
        self.icon_folder = os.path.dirname(self.icon_path) \
                                if self.icon_path is not None \
                                else None

        self.lutris_config = game.config
        self.game_config_id = game.config.game_config_id
        self.slug = game.slug
        self.runner_name = game.runner_name

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)

        self.build_notebook()
        self.build_tabs('game')
        self.build_action_area("Edit", self.on_save, callback)
        self.show_all()


class RunnerConfigDialog(Dialog, GameDialogCommon):
    """Runner config edit dialog."""
    def __init__(self, runner):
        self.runner_name = runner.__class__.__name__
        super(RunnerConfigDialog, self).__init__(
            "Configure %s" % self.runner_name
        )

        self.game = None
        self.saved = False
        self.lutris_config = LutrisConfig(runner_slug=self.runner_name)

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)

        self.build_notebook()
        self.build_tabs('runner')
        self.build_action_area("Edit", self.on_save)
        self.show_all()

    def on_save(self, wigdet, data=None):
        self.lutris_config.save()
        self.destroy()


class SystemConfigDialog(Dialog, GameDialogCommon):
    def __init__(self):
        super(SystemConfigDialog, self).__init__("System preferences")

        self.game = None
        self.runner_name = None
        self.lutris_config = LutrisConfig()

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)

        self.system_box = SystemBox(self.lutris_config)
        self.system_sw = self.build_scrolled_window(self.system_box)
        self.vbox.pack_start(self.system_sw, True, True, 0)
        self.build_action_area("Save", self.on_save)
        self.show_all()

    def on_save(self, widget):
        self.lutris_config.save()
        self.destroy()



