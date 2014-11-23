from gi.repository import Gtk, GdkPixbuf
from lutris import pga
from lutris.gui.widgets import get_runner_icon

LABEL = 0
ICON = 1


class SidebarTreeView(Gtk.TreeView):

    def __init__(self):
        self.model = Gtk.TreeStore(str, GdkPixbuf.Pixbuf)

        super(SidebarTreeView, self).__init__(model=self.model)

        column = Gtk.TreeViewColumn("Files")
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        text_renderer = Gtk.CellRendererText()
        icon_renderer = Gtk.CellRendererPixbuf()
        icon_renderer.set_property('stock-size', 16)
        column.pack_start(icon_renderer, False)
        column.pack_start(text_renderer, True)
        column.add_attribute(text_renderer, "text", LABEL)
        column.add_attribute(icon_renderer, "pixbuf", ICON)
        self.append_column(column)
        self.set_headers_visible(False)
        self.set_fixed_height_mode(True)

        self.get_runners()
        self.expand_all()

    def get_runners(self):
        runner_node = self.model.append(None, ["Runners", None])
        runners = pga.get_runners()
        for runner in runners:
            icon = get_runner_icon(runner, format='pixbuf', size=(16, 16))
            self.model.append(runner_node, [runner, icon])
