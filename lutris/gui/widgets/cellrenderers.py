from gi.repository import GObject, Gtk, Pango

from lutris.gui.views.media_loader import download_icons
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger


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
    def __init__(self, game_store, service_media, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.game_store = game_store
        self.service_media = service_media
        self.pending_download_slugs = set()

    @GObject.Property(type=str)
    def slug(self):
        return self._slug

    @slug.setter
    def slug(self, value):
        self._slug = value

    def do_render(self, cr, widget, background_area, cell_area, flags):
        service_media = self.service_media
        slug = self._slug

        if not service_media.exists(slug):
            self.pending_download_slugs.add(slug)

        Gtk.CellRendererPixbuf.do_render(self, cr, widget, background_area, cell_area, flags)

    def download_icons(self):
        service_media = self.service_media
        slugs = [slug for slug in self.pending_download_slugs if not service_media.exists(slug)]
        self.pending_download_slugs = set()

        if len(slugs) > 0:
            media_urls = service_media.get_media_urls()

            urls_needed = {
                slug: url
                for slug, url in media_urls.items()
                if slug in slugs
            }

            AsyncCall(
                download_icons,
                self.icons_download_cb,
                urls_needed,
                service_media
            )

    def icons_download_cb(self, result, error):
        if error:
            logger.error("Failed to download icons: %s", error)
            return
        self.game_store.update_icons(result)
