from gi.repository import Gtk, GdkPixbuf

import lutris.runners
from lutris import pga
from lutris.gui.runnerinstalldialog import RunnerInstallDialog
from lutris.gui.config_dialogs import RunnerConfigDialog
from lutris.gui.widgets import get_runner_icon

LABEL = 0
ICON = 1


class SidebarTreeView(Gtk.TreeView):
    def __init__(self):
        super(SidebarTreeView, self).__init__()

        self.model = Gtk.TreeStore(str, GdkPixbuf.Pixbuf)
        self.model_filter = self.model.filter_new()
        self.model_filter.set_visible_func(self.filter_rule)
        self.set_model(self.model_filter)

        column = Gtk.TreeViewColumn("Runners")
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)

        # Icon
        icon_renderer = Gtk.CellRendererPixbuf()
        icon_renderer.set_property('stock-size', 16)
        column.pack_start(icon_renderer, False)
        column.add_attribute(icon_renderer, "pixbuf", ICON)

        # Label
        text_renderer = Gtk.CellRendererText()
        column.pack_start(text_renderer, True)
        column.add_attribute(text_renderer, "text", LABEL)

        self.append_column(column)
        self.set_headers_visible(False)
        self.set_fixed_height_mode(True)

        self.connect('button-press-event', self.popup_contextual_menu)

        self.runners = lutris.runners.__all__
        self.used_runners = pga.get_used_runners()
        self.load_all_runners()
        self.update()
        self.expand_all()

    def load_all_runners(self):
        """Append runners to the model."""
        runner_node = self.model.append(None, ["Runners", None])
        for runner in self.runners:
            icon = get_runner_icon(runner, format='pixbuf', size=(16, 16))
            self.model.append(runner_node, [runner, icon])

    def get_selected_runner(self):
        """Return the selected runner's name."""
        selection = self.get_selection()
        if not selection:
            return
        model, iter = selection.get_selected()
        runner_name = model.get_value(iter, LABEL)
        if runner_name != 'Runners':
            return runner_name

    def filter_rule(self, model, iter, data):
        if model[iter][0] == 'Runners':
            return True
        return model[iter][0] in self.used_runners

    def update(self):
        self.used_runners = pga.get_used_runners()
        self.model_filter.refilter()

    def popup_contextual_menu(self, view, event):
        if event.button != 3:
            return
        view.current_path = view.get_path_at_pos(event.x, event.y)
        if view.current_path:
            view.set_cursor(view.current_path[0])
            runner_slug = self.get_selected_runner()
            if runner_slug not in self.runners:
                return
            ContextualMenu().popup(event, runner_slug, self.get_toplevel())


class ContextualMenu(Gtk.Menu):
    def __init__(self):
        super(ContextualMenu, self).__init__()

    def add_menuitems(self, entries):
        for entry in entries:
            name = entry[0]
            label = entry[1]
            action = Gtk.Action(name=name, label=label,
                                tooltip=None, stock_id=None)
            action.connect('activate', entry[2])
            menuitem = action.create_menu_item()
            menuitem.action_id = name
            self.append(menuitem)

    def popup(self, event, runner_slug, parent_window):
        self.runner = lutris.runners.import_runner(runner_slug)()
        self.parent_window = parent_window

        # Clear existing menu
        for item in self.get_children():
            self.remove(item)

        # Add items
        entries = [('configure', 'Configure', self.on_configure_runner)]
        if self.runner.multiple_versions:
            entries.append(('versions', 'Manage versions',
                            self.on_manage_versions))
        self.add_menuitems(entries)
        self.show_all()

        super(ContextualMenu, self).popup(None, None, None, None,
                                          event.button, event.time)

    def on_configure_runner(self, *args):
        RunnerConfigDialog(self.runner)

    def on_manage_versions(self, *args):
        dlg_title = "Manage %s versions" % self.runner.name
        dialog = RunnerInstallDialog(dlg_title, self.parent_window,
                                     self.runner.name)
        dialog.run()
        dialog.destroy()
