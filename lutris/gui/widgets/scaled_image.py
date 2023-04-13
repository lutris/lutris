from gi.repository import Gtk

from lutris.gui.widgets.utils import (
    ICON_SIZE, get_default_icon_path, get_pixbuf_by_path, get_runtime_icon_path, has_stock_icon
)
from lutris.util.log import logger


class ScaledImage(Gtk.Image):
    """This class provides a rather basic feature the GtkImage doesn't offer - the ability
    to scale the image rendered. Scaling a pixbuf is not the same thing - that discards
    pixel data. This will preserve it on high-DPI displays by scaling only at drawing time."""
    __gtype_name__ = 'ScaledImage'

    def __init__(self, scale_factor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scale_factor = scale_factor

    @staticmethod
    def new_scaled_from_path(path, size=None, preserve_aspect_ratio=True, scale_factor=1):
        """Constructs an image showing the image at the path, scaled to the size given.
        The scale factor is used to scale up the pixbuf, but scale down the image so
        a higher-res image can be shown in the same space on a High-DPI screen. You
        pass your widget's get_scale_factor() here."""

        pixbuf_size = (size[0] * scale_factor, size[1] * scale_factor) if size else None
        pixbuf = get_pixbuf_by_path(path, pixbuf_size)
        if not pixbuf:
            return None

        image = ScaledImage(1 / scale_factor)
        image.set_from_pixbuf(pixbuf)
        return image

    @staticmethod
    def new_from_media_path(path, size, scale_factor=1):
        """Constructs an image showing Lutris media, read from the path, scaled to the
         size given, as with new_scaled_from_path().

         However, if the path is not readable, this will substitute a default icon
         or banner. If 'size' is square, you get the icon; if not it is a gradient
        filling the full size given."""

        pixbuf_size = (size[0] * scale_factor, size[1] * scale_factor)
        pixbuf = get_pixbuf_by_path(path, pixbuf_size)
        if not pixbuf:
            default_icon = get_default_icon_path(size)
            pixbuf = get_pixbuf_by_path(default_icon, pixbuf_size, preserve_aspect_ratio=False)

            if not pixbuf:
                logger.error("The default media '%s' could not be loaded", default_icon)
                return None

        image = ScaledImage(1 / scale_factor)
        image.set_from_pixbuf(pixbuf)
        return image

    @staticmethod
    def get_runtime_icon_image(icon_name, fallback_stock_icon_name=None, scale_factor=1, visible=False):
        """Returns a ScaledImage of an icon for runtime or service; the image has the
        default icon size. If the icon can't be found, we'll fall back onto another,
        stock icon. If you don't supply one (or it's not available) we'll fall back
        further to 'package-x-generic-symbolic'; we always give you something."""
        path = get_runtime_icon_path(icon_name)
        icon = ScaledImage.new_scaled_from_path(path, size=ICON_SIZE, scale_factor=scale_factor)
        if not icon:
            if not has_stock_icon(fallback_stock_icon_name):
                fallback_stock_icon_name = "package-x-generic-symbolic"

            icon = Gtk.Image.new_from_icon_name(fallback_stock_icon_name, Gtk.IconSize.DND)
        icon.set_visible(visible)
        return icon

    def do_get_preferred_width(self):
        minimum, natural = Gtk.Image.do_get_preferred_width(self)
        return minimum * self.scale_factor, natural * self.scale_factor

    def do_get_preferred_height(self):
        minimum, natural = Gtk.Image.do_get_preferred_height(self)
        return minimum * self.scale_factor, natural * self.scale_factor

    def do_draw(self, cr):
        if self.scale_factor != 1:
            # we need to scale around the center of the image,
            # but cr.scale() scales around (0, 0). So we move
            # the co-ordinates before scaling.
            allocation = self.get_allocation()
            center_x = allocation.width / 2
            center_y = allocation.height / 2

            cr.translate(center_x, center_y)
            cr.scale(self.scale_factor, self.scale_factor)
            cr.translate(-center_x, -center_y)

        Gtk.Image.do_draw(self, cr)
