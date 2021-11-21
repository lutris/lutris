from gi.repository import GObject, Gtk, Pango
from gi.repository.GdkPixbuf import Pixbuf
from lutris.gui.views.media_loader import download_icons

class GridViewCellRendererText(Gtk.CellRendererText):
    """CellRendererText adjusted for grid view display, removes extra padding"""

    def __init__(self, width, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.props.alignment = Pango.Alignment.CENTER
        self.props.wrap_mode = Pango.WrapMode.WORD
        self.props.xalign = 0.5
        self.props.yalign = 0
        self.props.wrap_width = width

class GridViewCellRendererBanner(Gtk.CellRendererPixbuf):
    def __init__(self, service_media, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_media = service_media

    @GObject.Property(type=str)
    def slug(self):
        'Read-write integer property.'
        return self._slug

    @slug.setter
    def slug(self, value):
        self._slug = value

    def do_render(self, cr, widget, background_area, cell_area, flags):
        slug = self._slug

        media_urls = self.service_media.get_media_urls()
        url = media_urls[slug]
        download_icons({slug: url}, self.service_media)
        
        Gtk.CellRendererPixbuf.do_render(self, cr, widget, background_area, cell_area, flags)
  