from gi.repository import Gtk


class ScaledImage(Gtk.Image):
    """This class provides a rather basic feature the GtkImage doesn't offer- the ability
    to scale the image rendered. Scaling a pixbuf is not the same thing- that discards
    pixel data. This will preserve it on high-DPI displays by scaling only at drawing time."""
    __gtype_name__ = 'ScaledImage'

    def __init__(self, scale_factor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scale_factor = scale_factor

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
