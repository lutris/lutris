"""Tests for how installers are presented in the install dialog."""

from unittest import TestCase

from gi.repository import Gtk

from lutris.gui.installer.script_box import InstallerScriptBox
from lutris.util.test_config import setup_test_environment

setup_test_environment()

SCRIPT = {
    "runner": "wine",
    "version": "Standard (EUW)",
    "description": "",
    "notes": "",
    "credits": "",
}


def find_labels(widget):
    """Return all labels inside a widget"""
    if isinstance(widget, Gtk.Label):
        return [widget]
    if isinstance(widget, Gtk.Container):
        return [label for child in widget.get_children() for label in find_labels(child)]
    return []


def find_install_button(widget):
    if isinstance(widget, Gtk.Button):
        return widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            button = find_install_button(child)
            if button:
                return button
    return None


class TestNotPlayableInstallers(TestCase):
    def get_box(self, is_playable):
        return InstallerScriptBox({**SCRIPT, "is_playable": is_playable})

    def test_not_playable_installer_is_flagged(self):
        box = self.get_box(False)
        labels = [label.get_text() for label in find_labels(box)]
        self.assertIn("Not playable", labels)
        self.assertFalse(find_install_button(box).get_style_context().has_class("suggested-action"))

    def test_unrated_installer_is_not_flagged(self):
        for is_playable in (None, True):
            box = self.get_box(is_playable)
            labels = [label.get_text() for label in find_labels(box)]
            self.assertNotIn("Not playable", labels)
            self.assertTrue(find_install_button(box).get_style_context().has_class("suggested-action"))
