from gi.repository import Gtk, GdkPixbuf, GObject

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
GAMECOUNT = 4


class SidebarTreeView(Gtk.TreeView):
    def __init__(self):
        super(SidebarTreeView, self).__init__()
        self.installed_runners = []
        self.active_platforms = []

        self.model = Gtk.TreeStore(str, str, GdkPixbuf.Pixbuf, str, str)
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

        # Gamecount
        text_renderer3 = Gtk.CellRendererText()
        text_renderer3.set_alignment(1.0, 0.5)
        column.pack_start(text_renderer3, True)
        column.add_attribute(text_renderer3, "text", GAMECOUNT)

        self.append_column(column)
        self.set_headers_visible(False)
        self.set_fixed_height_mode(True)

        self.get_selection().set_mode(Gtk.SelectionMode.BROWSE)

        self.connect('button-press-event', self.popup_contextual_menu)
        GObject.add_emission_hook(RunnersDialog, "runner-installed", self.update)

        self.runners = sorted(runners.__all__)
        self.platforms = sorted(platforms.__all__)
        self.platform_node = None
        self.load_runners()
        self.load_platforms()
        self.update()
        self.expand_all()

    def load_runners(self):
        """Append runners to the model."""
        self.runner_node = self.model.append(None, ['runners', '', None, "All runners", None])
        for slug in self.runners:
            self.add_runner(slug)

    def add_runner(self, slug):
        name = runners.import_runner(slug).human_name
        icon = get_runner_icon(slug, format='pixbuf', size=(16, 16))
        self.model.append(self.runner_node, ['runners', slug, icon, name, None])

    def load_platforms(self):
        """Update platforms in the model."""
        self.platform_node = self.model.append(None, ['platforms', '', None, "All platforms", None])
        for platform in self.platforms:
            self.add_platform(platform)

    def add_platform(self, name):
        self.model.append(self.platform_node, ['platforms', name, None, name, None])

    def get_selected_filter(self):
        """Return the selected runner's name."""
        selection = self.get_selection()
        if not selection:
            return None
        model, iter = selection.get_selected()
        if not iter:
            return None
        type = model.get_value(iter, TYPE)
        slug = model.get_value(iter, SLUG)
        return type, slug

    def filter_rule(self, model, iter, data):
        if not model[iter][0]:
            return False
        if (model[iter][0] == 'runners' or model[iter][0] == 'platforms') and model[iter][1] == '':
            return True
        return (model[iter][0] == 'runners' and model[iter][1] in self.installed_runners) or \
               (model[iter][0] == 'platforms' and model[iter][1] in self.active_platforms)

    def update(self, *args):
        self.installed_runners = [runner.name for runner in runners.get_installed()]
        self.update_runners_game_count(pga.get_used_runners_game_count())
        self.active_platforms = pga.get_used_platforms()
        self.update_platforms_game_count(pga.get_used_platforms_game_count())
        self.model_filter.refilter()
        self.expand_all()
        # Return False here because this method is called with GLib.idle_add
        return False

    def update_runners_game_count(self, counts):
        runner_iter = self.model.iter_children(self.runner_node)
        self.update_iter_game_counts(runner_iter, counts)

    def update_platforms_game_count(self, counts):
        platform_iter = self.model.iter_children(self.platform_node)
        self.update_iter_game_counts(platform_iter, counts)

    def update_iter_game_counts(self, model_iter, counts):
        while model_iter is not None:
            slug = self.model.get_value(model_iter, SLUG)
            count = counts.get(slug, 0)
            count_display = "({0})".format(count)
            self.model.set_value(model_iter, GAMECOUNT, count_display)

            model_iter = self.model.iter_next(model_iter)

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
