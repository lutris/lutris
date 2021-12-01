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


class CellRendererBanner(Gtk.CellRendererPixbuf):
    """A renderer that causes banners and icons to download if they are to be drawn
    but do not exist (according to the service-media; we always get a pixbuf,
    which may be a placeholder, but if we get the slug, we'll double check it."""

    # We accumulate slugs to download for half a second so we can download in parallel
    pending_download_slugs = set()
    # We know what downloads are already coming, and don't ask for them again
    ongoing_download_slugs = set()
    # We know what downloads failed, and don't ask for them again.
    failed_slugs = set()
    # We avoid starting the timer twice, through it shuts down as soon as it fires.
    download_timer_running = False
    # Backing store for the slug property
    _slug = ""

    def __init__(self, game_store, service_media, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.game_store = game_store
        self.service_media = service_media

    @GObject.Property(type=str)
    def slug(self):
        """This property contains the slug to download, if required at render time."""
        return self._slug

    @slug.setter
    def slug(self, value):
        self._slug = value

    def do_render(self, cr, widget, background_area, cell_area, flags):
        # Before we render check the slug- if it needs to download, we'll
        # queue it up and start the timer. We do not download now- we]
        # render the pixbuf we were given. Downloads take too long to delay
        # rendering for.
        service_media = self.service_media
        slug = self._slug

        if slug and not service_media.exists(slug) and slug not in self.ongoing_download_slugs:
            CellRendererBanner.pending_download_slugs.add(slug)

            if not CellRendererBanner.download_timer_running:
                CellRendererBanner.download_timer_running = True
                GLib.timeout_add(500, self._download_pending)

        Gtk.CellRendererPixbuf.do_render(self, cr, widget, background_area, cell_area, flags)

    def _download_pending(self):
        """This is the timer function that is called shortly after rendering
        detects a needed download. It starts the downloads required."""
        CellRendererBanner.download_timer_running = False
        slugs = self.dequeue_pending_slugs()
        if len(slugs) > 0:
            self.download_for_slugs(slugs)
        return False  # one-shot timer

    def dequeue_pending_slugs(self):
        """Returns which slugs to download; we'll recheck that they
        are still needed, and are not downloading already or failed.
        But we clear the pending set in any case."""
        service_media = self.service_media
        slugs = [
            slug for slug
            in self.pending_download_slugs
            if slug not in CellRendererBanner.ongoing_download_slugs
            if slug not in CellRendererBanner.failed_slugs
            if not service_media.exists(slug)
        ]

        CellRendererBanner.pending_download_slugs.clear()
        return slugs

    def download_for_slugs(self, slugs):
        """Starts the download of the banners or icons for the slugs given."""
        service_media = self.service_media
        urls_needed = service_media.get_media_urls_for(slugs)

        def slugs_download_cb(result, error):
            """This is called when the download completes and records the 'icons';
            that will cause the UI to update and the cells, ultimately, to rerender."""
            CellRendererBanner.ongoing_download_slugs.difference_update(slugs)

            if error:
                CellRendererBanner.failed_slugs.update(slugs)
                logger.error("Failed to download icons: %s", error)
                return

            # Give the EGS service media chance to resize the banners it needs to-
            # but do this only when we're done downloading. It's going to examine
            # every banner file!
            if len(CellRendererBanner.ongoing_download_slugs) == 0:
                if len(CellRendererBanner.pending_download_slugs) == 0:
                    service_media.render()

            self.game_store.update_icons(result)

        CellRendererBanner.ongoing_download_slugs.update(slugs)

        AsyncCall(
            download_icons,
            slugs_download_cb,
            urls_needed,
            service_media
        )
