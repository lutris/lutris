from unittest import TestCase

import gi

gi.require_version('Gtk', '3.0')


from lutris.gui.application import Application


class TestPrint(TestCase):

    def setUp(self):
        self.lutris_application = Application()

    def test_print_steam_list(self):
        self.lutris_application.print_steam_list('cmd')

    def test_print_steam_folders(self):
        self.lutris_application.print_steam_folders('cmd')
