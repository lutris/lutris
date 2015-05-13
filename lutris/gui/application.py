import logging
from gettext import gettext as _
from gi.repository import GLib, Gio, Gtk

from lutris.util.log import logger
from lutris.config import check_config  # , register_handler
from lutris.game import Game
from lutris import pga
from lutris.settings import VERSION, GAME_CONFIG_DIR
from .installgamedialog import InstallerDialog
from .lutriswindow import LutrisWindow

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

    def do_activate(self):
        if not self.window:
            self.window = LutrisWindow()
            self.add_window(self.window.window)
        self.window.window.present()

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
        #self.quit()

