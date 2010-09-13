import os
import gtk
import pango
import lutris.constants


ICON_SIZE = 24
MISSING_APP_ICON = "/usr/share/icons/gnome/24x24/categories/applications-other.png"

class GameTreeView(gtk.TreeView):
    (COL_ICON,
     COL_TEXT) = range(2)

   
    def __init__(self, games):
        super(GameTreeView, self).__init__()
        model = gtk.ListStore(gtk.gdk.Pixbuf, str, str)
        self.set_model(model)
        tp = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("Icon", tp, pixbuf=self.COL_ICON)
        self.append_column(column)
        tr = gtk.CellRendererText()
        tr.set_property("ellipsize", pango.ELLIPSIZE_END)
        column = gtk.TreeViewColumn("Game", tr, markup=self.COL_TEXT)
        self.append_column(column)
        for game in sorted(games):
            s = "%s \n<small>%s</small>" % (
                    game['name'], game['runner'])
            icon_path = os.path.join(lutris.constants.DATA_PATH, 'media/runner_icons', game['runner'] + '.png')
            pix = gtk.gdk.pixbuf_new_from_file_at_size(icon_path, 
                                                       ICON_SIZE, ICON_SIZE)
            row = model.append([pix, s, game['id']])

