#!/usr/bin/python2
# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-

import logging
import json
import os
import dialogs

from gi.repository import GLib, Gio, Gtk

from lutris.util import datapath
from lutris.util.log import logger
from lutris.config import check_config
from lutris.game import Game
from lutris import pga
from lutris.settings import VERSION, GAME_CONFIG_DIR
from lutris.gui.installgamedialog import InstallerDialog
from lutris.gui.lutriswindow import LutrisWindow
from lutris.gui.runnersdialog import RunnersDialog
from lutris.gui.config_dialogs import SystemConfigDialog


class Application(Gtk.Application):
    def __init__(self):
        Gtk.Application.__init__(
                self, application_id='net.lutris',
                flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        GLib.set_application_name('Lutris')
        self.window = None

        self.add_main_option(
                 "verbose", "v", GLib.OptionFlags.NONE,
                 GLib.OptionArg.NONE, "Verbose output", None)
        self.add_main_option(
                 "debug", "d", GLib.OptionFlags.NONE,
                 GLib.OptionArg.NONE, "Show debug messages", None)
        self.add_main_option(
                 "install", "i", GLib.OptionFlags.NONE,
                 GLib.OptionArg.NONE, "Install a game from a yml file", None)
        self.add_main_option(
                 "list-games", "l", GLib.OptionFlags.NONE,
                 GLib.OptionArg.NONE, "List games in database", None)
        self.add_main_option(
                 "installed", "o", GLib.OptionFlags.NONE,
                 GLib.OptionArg.NONE, "Only list installed games", None)
        self.add_main_option(
                 "list-steam", "s", GLib.OptionFlags.NONE,
                 GLib.OptionArg.NONE, "List Steam (Windows) games", None)
        self.add_main_option(
                 "json", "j", GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                 "Display the list of games in JSON format", None)
        self.add_main_option(
                 "reinstall", '\0', GLib.OptionFlags.NONE,
                 GLib.OptionArg.NONE, "Reinstall game", None)
        self.add_main_option(
                 GLib.OPTION_REMAINING, '\0', GLib.OptionFlags.NONE,
                 GLib.OptionArg.STRING_ARRAY, '"lutris:" uri to open', 'URI')

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
            gtk.StyleContext.add_provider_for_screen(self.window.get_screen(), provider, 600)
        self.window.window.present()

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()

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
            game_list = pga.get_games()
            if options.contains('list_installed'):
                game_list = [game for game in game_list if game['installed']]
            if options.contains('json'):
                games = []
                for game in game_list:
                    games.append({
                        'id': game['id'],
                        'slug': game['slug'],
                        'name': game['name'],
                        'runner': game['runner'],
                        'directory': game['directory'] or '-'
                    })
                    print json.dumps(games, indent=2).encode('utf-8')
            else:
                for game in game_list:
                    print u"{:4} | {:<40} | {:<40} | {:<15} | {:<64}".format(
                        game['id'],
                        game['name'][:40],
                        game['slug'][:40],
                        game['runner'],
                        game['directory'] or '-'
                    ).encode('utf-8')
            exit()

        if options.contains('list-steam'):
            from lutris.runners import winesteam
            steam_runner = winesteam.winesteam()
            print steam_runner.get_appid_list()
            exit()



        self.activate()
        return 0

    def do_shutdown(self):
        Gtk.Application.do_shutdown(self)
        self.quit()

    def on_about(self, action, param):
        dialogs.AboutDialog()

    def on_preferences(self, action, param):
        SystemConfigDialog()

    def on_runners(self, action, param):
        RunnersDialog()

    def on_pga(self, action, param):
        dialogs.PgaSourceDialog()

    def on_quit(self, action, param):
        self.quit()
