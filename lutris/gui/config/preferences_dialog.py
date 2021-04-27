"""Configuration dialog for client and system options"""
from gettext import gettext as _

from gi.repository import Gtk

from lutris.config import LutrisConfig
from lutris.gui.config.boxes import SystemBox
from lutris.gui.config.common import GameDialogCommon
from lutris.gui.config.preferences_box import PreferencesBox
from lutris.gui.config.runners_box import RunnersBox
from lutris.gui.config.sysinfo_box import SysInfoBox


# pylint: disable=no-member
class PreferencesDialog(GameDialogCommon):
    def __init__(self, parent=None):
        super().__init__(_("Lutris settings"), parent=parent)
        self.set_border_width(0)
        self.set_default_size(960, 600)
        self.lutris_config = LutrisConfig()

        hbox = Gtk.HBox(visible=True)
        sidebar = Gtk.ListBox(visible=True)
        sidebar.connect("row-selected", self.on_sidebar_activated)
        sidebar.add(self.get_sidebar_button("prefs-stack", "Interface", "view-grid-symbolic"))
        sidebar.add(self.get_sidebar_button("runners-stack", "Runners", "applications-utilities-symbolic"))
        sidebar.add(self.get_sidebar_button("sysinfo-stack", "Hardware information", "computer-symbolic"))
        sidebar.add(self.get_sidebar_button("system-stack", "Global options", "emblem-system-symbolic"))
        hbox.pack_start(sidebar, False, False, 0)
        self.stack = Gtk.Stack(visible=True)
        self.stack.set_vhomogeneous(False)
        self.stack.set_interpolate_size(True)
        hbox.add(self.stack)
        self.vbox.pack_start(hbox, True, True, 0)
        self.stack.add_titled(
            self.build_scrolled_window(PreferencesBox()),
            "prefs-stack",
            _("Lutris preferences")
        )
        self.stack.add_titled(
            self.build_scrolled_window(RunnersBox()),
            "runners-stack",
            _("Runners")
        )
        self.stack.add_titled(
            self.build_scrolled_window(SysInfoBox()),
            "sysinfo-stack",
            _("System Information")
        )
        self.system_box = SystemBox(self.lutris_config)
        self.system_box.show_all()
        self.stack.add_titled(
            self.build_scrolled_window(self.system_box),
            "system-stack",
            _("System options")
        )
        self.build_action_area(self.on_save)
        self.action_area.set_margin_bottom(12)
        self.action_area.set_margin_right(12)
        self.action_area.set_margin_left(12)
        self.action_area.set_margin_top(12)

    def on_sidebar_activated(self, _listbox, row):
        if row.get_children()[0].stack_id == "system-stack":
            self.action_area.show_all()
        else:
            self.action_area.hide()
        self.stack.set_visible_child_name(row.get_children()[0].stack_id)

    def get_sidebar_button(self, stack_id, text, icon_name):
        hbox = Gtk.HBox(visible=True)
        hbox.stack_id = stack_id
        hbox.set_margin_top(12)
        hbox.set_margin_bottom(12)
        hbox.set_margin_right(40)

        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        icon.show()
        hbox.pack_start(icon, False, False, 6)

        label = Gtk.Label(text, visible=True)
        label.set_alignment(0, 0.5)
        hbox.pack_start(label, False, False, 6)
        return hbox

    def on_save(self, _widget):
        self.lutris_config.save()
        self.destroy()
