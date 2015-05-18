import os
import logging
from gettext import gettext as _
from gi.repository import GLib, Gio, Gtk

from lutris.util import datapath
from lutris.util.log import logger
from lutris.config import check_config  # , register_handler
from lutris.game import Game
from lutris import pga
from lutris.settings import VERSION, GAME_CONFIG_DIR
import dialogs
from .runnersdialog import RunnersDialog
from .installgamedialog import InstallerDialog
from .lutriswindow import LutrisWindow
from .config_dialogs import SystemConfigDialog

class Application(Gtk.Application):

    def __init__(self):
        Gtk.Application.__init__(self, application_id='net.lutris',
                                 flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        GLib.set_application_name(_('Lutris'))
        self.window = None

        self.add_main_option('verbose', 'v', GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             _('Verbose output'), None)
        self.add_main_option('debug', 'd', GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             _('Show debug messages'), None)
        self.add_main_option('install', 'i', GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             _('Install a game from a yml file'), None)
        self.add_main_option('list-games', 'l', GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             _('List all games in database'), None)
        self.add_main_option('list-steam', 's', GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             _('List Steam (Windows) games'), None)
        self.add_main_option('reinstall', '\0', GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             _('Reinstall game'), None)
        self.add_main_option(GLib.OPTION_REMAINING, '\0', GLib.OptionFlags.NONE, GLib.OptionArg.STRING_ARRAY,
                             _('"lutris:" uri to open'), 'URI')

    def do_startup(self):
        Gtk.Application.do_startup(self)

        action = Gio.SimpleAction.new('preferences', None)
        action.connect('activate', self.on_preferences)
        self.add_action(action)

        action = Gio.SimpleAction.new('runners', None)
        action.connect('activate', self.on_runners)
        self.add_action(action)

        action = Gio.SimpleAction.new('pga', None)
        action.connect('activate', self.on_pga)
        self.add_action(action)

        action = Gio.SimpleAction.new('about', None)
        action.connect('activate', self.on_about)
        self.add_action(action)

        action = Gio.SimpleAction.new('quit', None)
        action.connect('activate', self.on_quit)
        self.add_action(action)

        builder = Gtk.Builder.new_from_file(os.path.join(datapath.get(), 'gtk', 'menus.ui'))
        appmenu = builder.get_object('app-menu')
        self.set_app_menu(appmenu)

    def do_activate(self):
        if not self.window:
            self.window = LutrisWindow(self).window
            provider = Gtk.CssProvider()
            provider.load_from_path(os.path.join(datapath.get(), 'ui', 'style.css'))
            Gtk.StyleContext.add_provider_for_screen(self.window.get_screen(), provider, 600)

        self.window.present()

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()

        # Set the logging level to show debug messages.
        console = logging.StreamHandler()
        fmt = '%(levelname)-8s %(asctime)s [%(module)s]:%(message)s'
        formatter = logging.Formatter(fmt)
        console.setFormatter(formatter)
        logger.addHandler(console)
        logger.setLevel(logging.ERROR)

        if options.contains('verbose'):
            logger.setLevel(logging.INFO)

        if options.contains('debug'):
            logger.setLevel(logging.DEBUG)

        if options.contains('list-games'):
            for game in pga.get_games():
                command_line.do_print_literal(command_line, u'{:<40} | {:<40} | {:<15} | {:<64}\n'.format(
                    game['name'][:40],
                    game['slug'][:40],
                    game['runner'],
                    game['directory'] or '-'
                ).encode('utf-8'))
            return 0

        if options.contains('list-steam'):
            from lutris.runners import winesteam
            steam_runner = winesteam.winesteam()
            appid_list = steam_runner.get_appid_list()
            if app_id_list:
                command_line.do_print_literal(command_line, appid_list + '\n')
            else:
                command_line.do_printerr_literal(command_line, _('No Steam games found.\n'))
            return 0

        check_config(force_wipe=False)
        game_slug = ''
        uri = options.lookup_value(GLib.OPTION_REMAINING)
        if uri and len(uri):
            uri = uri[0] # TODO: Support multiple
            if not uri.startswith('lutris:'):
                command_line.do_printerr_literal(command_line, '%s is not a valid URI\n' %uri)
                return 1
            game_slug = uri[7:]

        if game_slug or options.contains('installer_file'):
            file_path = os.path.join(GAME_CONFIG_DIR, game_slug + ".yml")
            db_game = pga.get_game_by_slug(game_slug) \
                or pga.get_game_by_slug(game_slug, field='installer_slug')
            if db_game and db_game['installed'] and not options.contains('reinstall'):
                logger.info("Launching %s", db_game['name'])
                lutris_game = Game(db_game['slug'])
                lutris_game.play()
                return 0
            else:
                logger.info("Installing %s", game_slug)
                InstallerDialog(options.lookup_value('installer_file') or game_slug)
                return 0

        self.activate()
        return 0

    def do_shutdown(self):
        Gtk.Application.do_shutdown(self)
        self.quit()

    def on_about(self, action, param):
        dialogs.AboutDialog(parent=self.window)

    def on_preferences(self, action, param):
        SystemConfigDialog(parent=self.window)

    def on_runners(self, action, param):
        RunnersDialog()

    def on_pga(self, action, param):
        dialogs.PgaSourceDialog(parent=self.window)

    def on_quit(self, action, param):
        self.quit()

