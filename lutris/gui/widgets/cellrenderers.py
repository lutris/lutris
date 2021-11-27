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
        self.ongoing_download_slugs = set()
        self.failed_slugs = set()
        self._slug = ""
        self.draw_widget = None
        self.draw_connection_id = None

    @GObject.Property(type=str)
    def slug(self):
        return self._slug

    @slug.setter
    def slug(self, value):
        self._slug = value

    def do_render(self, cr, widget, background_area, cell_area, flags):
        service_media = self.service_media
        slug = self._slug

        if slug and not service_media.exists(slug) and slug not in self.ongoing_download_slugs:
            self.pending_download_slugs.add(slug)

            if self.draw_connection_id is None:
                self.draw_widget = widget
                self.draw_connection_id = widget.connect("draw", self.on_widget_draw)

        Gtk.CellRendererPixbuf.do_render(self, cr, widget, background_area, cell_area, flags)

    def download_icons(self):
        service_media = self.service_media
        slugs = [
            slug for slug
            in self.pending_download_slugs
            if slug not in self.ongoing_download_slugs
            if slug not in self.failed_slugs
            if not service_media.exists(slug)
        ]

        self.pending_download_slugs = set()

        if len(slugs) == 0:
            return

        urls_needed = service_media.get_media_urls_for(slugs)

        if len(urls_needed) == 0:
            return

        self.ongoing_download_slugs.update(slugs)

        def icons_download_cb(result, error):
            self.ongoing_download_slugs.difference_update(slugs)

            if error:
                self.failed_slugs.update(slugs)
                logger.error("Failed to download icons: %s", error)
                return
            self.game_store.update_icons(result)

        AsyncCall(
            download_icons,
            icons_download_cb,
            urls_needed,
            service_media
        )

    def on_widget_draw(self, _view, cr):
        self.draw_widget.disconnect(self.draw_connection_id)
        self.draw_widget = None
        self.draw_connection_id = None
        self.download_icons()
