from gi.repository import Gtk, Gdk, GdkPixbuf, GObject

from lutris import runners
from lutris import platforms
from lutris import pga
from lutris.gui.runnerinstalldialog import RunnerInstallDialog
from lutris.gui.config_dialogs import RunnerConfigDialog
from lutris.gui.runnersdialog import RunnersDialog
from lutris.gui.widgets.utils import get_runner_icon

TYPE = 0
SLUG = 1
ICON = 2
LABEL = 3


class SidebarRow(Gtk.ListBoxRow):
    def __init__(self, id_, type_, name, icon):
        super().__init__()
        self.get_style_context().add_class('sidebar-row')
        self.type = type_
        self.id = id_

        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 5)
        icon = Gtk.Image.new_from_pixbuf(icon)
        box.add(icon)
        label = Gtk.Label(label=name, halign=Gtk.Align.START, hexpand=True)
        box.add(label)
        self.add(box)


class SidebarHeader(Gtk.Box):
    def __init__(self, name):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.get_style_context().add_class('sidebar-header')
        label = Gtk.Label(halign=Gtk.Align.START, hexpand=True, label=name)
        if name == 'Runners':
            box = Gtk.Box()
            box.add(label)
            btn = Gtk.Button.new_from_icon_name('emblem-system-symbolic',
                                                Gtk.IconSize.MENU)
            btn.props.action_name = 'win.manage-runners'
            btn.props.relief = Gtk.ReliefStyle.NONE
            box.add(btn)
            self.add(box)
        else:
            self.add(label)
        self.add(Gtk.Separator())
        self.show_all()


class SidebarListBox(Gtk.ListBox):
    def __init__(self):
        super().__init__()
        self.get_style_context().add_class('sidebar')
        self.installed_runners = []
        self.active_platforms = pga.get_used_platforms()
        self.runners = sorted(runners.__all__)
        self.platforms = sorted(platforms.__all__)

        GObject.add_emission_hook(RunnersDialog, "runner-installed", self.update)

        all_row = SidebarRow(None, 'runner', 'All', None)
        self.add(all_row)
        self.select_row(all_row)
        for runner in self.runners:
            icon = get_runner_icon(runner, format='pixbuf', size=(16, 16))
            name = runners.import_runner(runner).human_name
            self.add(SidebarRow(runner, 'runner', name, icon))

        self.add(SidebarRow(None, 'platform', 'All', None))
        for platform in self.platforms:
            self.add(SidebarRow(platform, 'platform', platform, None))

        self.set_filter_func(self._filter_func)
        self.set_header_func(self._header_func)
        self.update()
        self.show_all()

    def _filter_func(self, row):
        if row is None:
            return True
        elif row.type == 'runner':
            if row.id is None:
                return True  # 'All'
            return row.id in self.installed_runners
        else:
            if len(self.active_platforms) <= 1:
                return False  # Hide useless filter
            elif row.id is None:  # 'All'
                return True
            return row.id in self.active_platforms

    def _header_func(self, row, before):
        if row.get_header():
            return

        if not before:
            row.set_header(SidebarHeader('Runners'))
        elif before.type == 'runner' and row.type == 'platform':
            row.set_header(SidebarHeader('Platforms'))

    def do_button_press_event(self, event):
        row = self.get_row_at_y(event.y)
        if not event.triggers_context_menu() or not row:
            return Gtk.ListBoxRow.do_button_press_event(self, event)

        self.select_row(row)
        if row.id and row.type == 'runner':
            menu = ContextualMenu()
            menu.popup(event, row.id, self.get_toplevel())
        return Gdk.EVENT_STOP

    def update(self, *args):
        self.installed_runners = [runner.name for runner in runners.get_installed()]
        self.active_platforms = pga.get_used_platforms()
        self.invalidate_filter()


class ContextualMenu(Gtk.Menu):
    def __init__(self):
        super().__init__()

    def add_menuitems(self, entries):
        for entry in entries:
            name = entry[0]
            label = entry[1]
            action = Gtk.Action(name=name, label=label)
            action.connect('activate', entry[2])
            menuitem = action.create_menu_item()
            menuitem.action_id = name
            self.append(menuitem)

    def popup(self, event, runner_slug, parent_window):
        self.runner = runners.import_runner(runner_slug)()
        self.parent_window = parent_window

        # Clear existing menu
        for item in self.get_children():
            self.remove(item)

        # Add items
        entries = [('configure', 'Configure', self.on_configure_runner)]
        if self.runner.multiple_versions:
            entries.append(('versions', 'Manage versions',
                            self.on_manage_versions))
        if self.runner.runnable_alone:
            entries.append(('run', 'Run', self.runner.run))
        self.add_menuitems(entries)
        self.show_all()

        super().popup(None, None, None, None, event.button, event.time)

    def on_configure_runner(self, *args):
        RunnerConfigDialog(self.runner, parent=self.parent_window)

    def on_manage_versions(self, *args):
        dlg_title = "Manage %s versions" % self.runner.name
        RunnerInstallDialog(dlg_title, self.parent_window, self.runner.name)
