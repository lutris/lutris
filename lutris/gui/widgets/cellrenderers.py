from gi.repository import GLib, GObject, Gtk, Pango

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
    pending_download_slugs = set()
    ongoing_download_slugs = set()
    failed_slugs = set()
    download_timer_running = False
    _slug = ""

    def __init__(self, game_store, service_media, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.game_store = game_store
        self.service_media = service_media

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

            if not self.download_timer_running:
                self.download_timer_running = True
                GLib.timeout_add(500, self.on_widget_timeout)

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

            # Give the EGS service media chance to resize the banners it needs to-
            # but do this only when we're done downloading. It's going to examine
            # every banner file!
            if len(self.ongoing_download_slugs) == 0 and len(self.pending_download_slugs) == 0:
                service_media.render()

            self.game_store.update_icons(result)

        AsyncCall(
            download_icons,
            icons_download_cb,
            urls_needed,
            service_media
        )

    def on_widget_timeout(self):
        self.download_timer_running = False
        self.download_icons()
        return False
