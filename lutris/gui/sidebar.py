from gi.repository import Gtk, GdkPixbuf

import lutris.runners
from lutris import pga
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

        self.used_runners = pga.get_used_runners()
        self.load_all_runners()
        self.update()
        self.expand_all()

    def load_all_runners(self):
        """Append runners to the model."""
        runner_node = self.model.append(None, ["Runners", None])
        runners = lutris.runners.__all__
        for runner in runners:
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
