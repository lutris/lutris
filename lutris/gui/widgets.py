import os
import gtk
import pango
import lutris.constants


ICON_SIZE = 24
MISSING_APP_ICON = "/usr/share/icons/gnome/24x24/categories/applications-other.png"

class GameTreeView(gtk.TreeView):
    COL_ICON = 1
    COL_TEXT = 2

    def __init__(self, games):
        super(GameTreeView, self).__init__()
        model = gtk.ListStore(str,gtk.gdk.Pixbuf, str)
        model.set_sort_column_id(0, gtk.SORT_ASCENDING)
        self.set_model(model)
        tp = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("Runner", tp, pixbuf=self.COL_ICON)
        self.append_column(column)
        tr = gtk.CellRendererText()
        tr.set_property("ellipsize", pango.ELLIPSIZE_END)
        column = gtk.TreeViewColumn("Game", tr, markup=self.COL_TEXT)
        self.append_column(column)
        for game in sorted(games):
            self.add_row(game)

    def add_row(self, game):
        model = self.get_model()
        s = "%s \n<small>%s</small>" % (
                game['name'], game['runner'])
        icon_path = os.path.join(lutris.constants.DATA_PATH, 'media/runner_icons', game['runner'] + '.png')
        pix = gtk.gdk.pixbuf_new_from_file_at_size(icon_path,
                                                   ICON_SIZE, ICON_SIZE)
        row = model.append([game['id'], pix, s,])
        return row

    def remove_row(self, model_iter):
        model = self.get_model()
        model.remove(model_iter)
        

    def sort_rows(self):
        model = self.get_model()
        gtk.TreeModelSort(model)
