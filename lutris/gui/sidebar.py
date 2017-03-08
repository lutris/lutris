from gi.repository import Gtk, GdkPixbuf, GObject

from lutris import runners
from lutris import platforms
from lutris.gui.runnerinstalldialog import RunnerInstallDialog
from lutris.gui.config_dialogs import RunnerConfigDialog
from lutris.gui.runnersdialog import RunnersDialog
from lutris.gui.installgamedialog import InstallerDialog
from lutris.gui.widgets import get_runner_icon

TYPE = 0
SLUG = 1
ICON = 2
LABEL = 3


class SidebarTreeView(Gtk.TreeView):
    def __init__(self):
        super(SidebarTreeView, self).__init__()
        self.installed_runners = []
        self.active_platforms = []

        self.model = Gtk.TreeStore(str, str, GdkPixbuf.Pixbuf, str)
        self.model_filter = self.model.filter_new()
        self.model_filter.set_visible_func(self.filter_rule)
        self.set_model(self.model_filter)

        column = Gtk.TreeViewColumn("Runners")
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)

        # Type
        type_renderer = Gtk.CellRendererText()
        type_renderer.set_visible(False)
        column.pack_start(type_renderer, True)
        column.add_attribute(type_renderer, "text", TYPE)

        # Runner slug
        text_renderer = Gtk.CellRendererText()
        text_renderer.set_visible(False)
        column.pack_start(text_renderer, True)
        column.add_attribute(text_renderer, "text", SLUG)

        # Icon
        icon_renderer = Gtk.CellRendererPixbuf()
        icon_renderer.set_property('width', 20)
        column.pack_start(icon_renderer, False)
        column.add_attribute(icon_renderer, "pixbuf", ICON)

        # Label
        text_renderer2 = Gtk.CellRendererText()
        column.pack_start(text_renderer2, True)
        column.add_attribute(text_renderer2, "text", LABEL)

        self.append_column(column)
        self.set_headers_visible(False)
        self.set_fixed_height_mode(True)

        self.get_selection().set_mode(Gtk.SelectionMode.BROWSE)

        self.connect('button-press-event', self.popup_contextual_menu)
        GObject.add_emission_hook(RunnersDialog, "runner-installed", self.update)

        self.runners = sorted(runners.__all__)
        self.platforms = sorted(platforms.__all__)
        self.platform_node = None
        self.load_all_runners()
        self.load_all_platforms()
        self.update()
        self.expand_all()

    def load_all_runners(self):
        """Append runners to the model."""
        self.runner_node = self.model.append(None, ['runners', '', None, "All runners"])
        for slug in self.runners:
            self.add_runner(slug)

    def add_runner(self, slug):
        name = runners.import_runner(slug).human_name
        icon = get_runner_icon(slug, format='pixbuf', size=(16, 16))
        self.model.append(self.runner_node, ['runners', slug, icon, name])

    def get_selected_filter(self):
        """Return the selected runner's name."""
        selection = self.get_selection()
        if not selection:
            return
        model, iter = selection.get_selected()
        if not iter:
            return
        type = model.get_value(iter, TYPE)
        slug = model.get_value(iter, SLUG)
        return (type, slug)

    def load_all_platforms(self):
        """Update platforms in the model."""
        data = ['platforms', '', None, "All platforms"]

        self.platform_node = self.model.append(None, data)

        for platform in self.platforms:
            self.add_platform(platform)

    def add_platform(self, name):
        self.model.append(self.platform_node, [
            'platforms',
            name,
            None,
            name.replace(' / ', ' ')
        ])

    def filter_rule(self, model, iter, data):
        if not model[iter][0]:
            return False
        if (model[iter][0] == 'runners' or model[iter][0] == 'platforms') and model[iter][1] == '':
            return True
        return (model[iter][0] == 'runners' and model[iter][1] in self.installed_runners) or \
               (model[iter][0] == 'platforms' and model[iter][1] in self.active_platforms)

    def update(self, *args):
        self.installed_runners = [runner.name for runner in runners.get_installed()]
        self.active_platforms = [platform for platform in platforms.get_active()]
        self.model_filter.refilter()
        self.expand_all()
        return True

    def popup_contextual_menu(self, view, event):
        if event.button != 3:
            return
        view.current_path = view.get_path_at_pos(event.x, event.y)
        if view.current_path:
            view.set_cursor(view.current_path[0])
            type, slug = self.get_selected_filter()
            if type != 'runners' or not slug or slug not in self.runners:
                return
            menu = ContextualMenu()
            menu.popup(event, slug, self.get_toplevel())


class ContextualMenu(Gtk.Menu):
    def __init__(self):
        super(ContextualMenu, self).__init__()

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

        super(ContextualMenu, self).popup(None, None, None, None,
                                          event.button, event.time)

    def on_configure_runner(self, *args):
        RunnerConfigDialog(self.runner, parent=self.parent_window)

    def on_manage_versions(self, *args):
        dlg_title = "Manage %s versions" % self.runner.name
        RunnerInstallDialog(dlg_title, self.parent_window, self.runner.name)
