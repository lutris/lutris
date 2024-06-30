"""Configuration dialog for client and system options"""

# pylint: disable=no-member
from gettext import gettext as _
from textwrap import dedent

from gi.repository import GObject, Gtk

from lutris.config import LutrisConfig
from lutris.gui.config.accounts_box import AccountsBox
from lutris.gui.config.boxes import SystemConfigBox
from lutris.gui.config.game_common import GameDialogCommon
from lutris.gui.config.preferences_box import InterfacePreferencesBox
from lutris.gui.config.runners_box import RunnersBox
from lutris.gui.config.services_box import ServicesBox
from lutris.gui.config.storage_box import StorageBox
from lutris.gui.config.sysinfo_box import SystemBox
from lutris.gui.config.updates_box import UpdatesBox


class PreferencesDialog(GameDialogCommon):
    __gsignals__ = {
        "settings-changed": (GObject.SIGNAL_RUN_LAST, None, (bool, str)),
    }

    def __init__(self, parent=None):
        super().__init__(_("Lutris settings"), config_level="system", parent=parent)
        self.set_border_width(0)
        self.set_default_size(1010, 600)
        self.lutris_config = LutrisConfig()
        self.page_generators = {}

        self.accelerators = Gtk.AccelGroup()
        self.add_accel_group(self.accelerators)

        hbox = Gtk.HBox(visible=True)
        sidebar = Gtk.ListBox(visible=True)
        sidebar.connect("row-selected", self.on_sidebar_activated)
        sidebar.add(self.get_sidebar_button("prefs-stack", _("Interface"), "view-grid-symbolic"))
        sidebar.add(self.get_sidebar_button("runners-stack", _("Runners"), "applications-utilities-symbolic"))
        sidebar.add(self.get_sidebar_button("services-stack", _("Sources"), "application-x-addon-symbolic"))
        sidebar.add(self.get_sidebar_button("accounts-stack", _("Accounts"), "system-users-symbolic"))
        sidebar.add(self.get_sidebar_button("updates-stack", _("Updates"), "system-software-install-symbolic"))
        sidebar.add(self.get_sidebar_button("sysinfo-stack", _("System"), "computer-symbolic"))
        sidebar.add(self.get_sidebar_button("storage-stack", _("Storage"), "drive-harddisk-symbolic"))
        sidebar.add(self.get_sidebar_button("system-stack", _("Global options"), "emblem-system-symbolic"))
        hbox.pack_start(sidebar, False, False, 0)
        self.stack = Gtk.Stack(visible=True)
        self.stack.set_vhomogeneous(False)
        self.stack.set_interpolate_size(True)
        hbox.add(self.stack)
        self.vbox.pack_start(hbox, True, True, 0)
        self.vbox.set_border_width(0)  # keep everything flush with the window edge
        self.stack.add_named(self.build_scrolled_window(InterfacePreferencesBox(self.accelerators)), "prefs-stack")

        self.runners_box = RunnersBox()
        self.page_generators["runners-stack"] = self.runners_box.populate_runners
        self.stack.add_named(self.build_scrolled_window(self.runners_box), "runners-stack")

        services_box = ServicesBox()
        self.page_generators["services-stack"] = services_box.populate_services
        self.stack.add_named(self.build_scrolled_window(services_box), "services-stack")

        accounts_box = AccountsBox()
        self.page_generators["accounts-stack"] = accounts_box.populate_steam_accounts
        self.stack.add_named(self.build_scrolled_window(accounts_box), "accounts-stack")

        updates_box = UpdatesBox()
        self.page_generators["updates-stack"] = updates_box.populate
        self.stack.add_named(self.build_scrolled_window(updates_box), "updates-stack")

        sysinfo_box = SystemBox()
        self.page_generators["sysinfo-stack"] = sysinfo_box.populate
        self.stack.add_named(self.build_scrolled_window(sysinfo_box), "sysinfo-stack")

        storage_box = StorageBox()
        self.page_generators["storage-stack"] = storage_box.populate
        self.stack.add_named(self.build_scrolled_window(storage_box), "storage-stack")

        self.system_box = SystemConfigBox(self.config_level, self.lutris_config)
        self.page_generators["system-stack"] = self.system_box.generate_widgets
        self.stack.add_named(self.build_scrolled_window(self.system_box), "system-stack")

    def on_sidebar_activated(self, _listbox, row):
        stack_id = row.get_children()[0].stack_id

        generator = self.page_generators.get(stack_id)

        if generator:
            del self.page_generators[stack_id]
            generator()

        show_actions = stack_id == "system-stack"
        self.set_header_bar_widgets_visibility(show_actions)

        if stack_id == "system-stack":
            self.set_search_entry_visibility(True)
        elif stack_id == "runners-stack":
            tooltip_markup = """
            Enter the name or description of a runner to search for, or use search terms:

            <b>installed:</b><i>true</i>	    Only installed runners.
            """
            tooltip_markup = dedent(tooltip_markup).strip()
            self.set_search_entry_visibility(
                True, self.runners_box.search_entry_placeholder_text, tooltip_markup=tooltip_markup
            )
        else:
            self.set_search_entry_visibility(False)

        self.get_header_bar().set_show_close_button(not show_actions)
        self.stack.set_visible_child_name(row.get_children()[0].stack_id)

    def get_search_entry_placeholder(self):
        return _("Search global options")

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

    def _set_filter(self, value):
        super()._set_filter(value)
        self.runners_box.filter = value
