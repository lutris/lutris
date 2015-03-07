from gi.repository import Gtk, Pango, GObject


class GridViewCellRendererText(Gtk.CellRendererText):
    """CellRendererText adjusted for grid view display, removes extra padding"""
    def __init__(self, width=None, *args, **kwargs):
        super(GridViewCellRendererText, self).__init__(*args, **kwargs)
        self.props.alignment = Pango.Alignment.CENTER
        self.props.wrap_mode = Pango.WrapMode.WORD
        self.props.xalign = 0.5
        self.props.yalign = 0
        self.props.width = width
        self.props.wrap_width = width


class CellRendererButton(Gtk.CellRenderer):
    value = GObject.Property(
        type=str,
        nick='value',
        blurb='what data to render',
        flags=(GObject.PARAM_READWRITE | GObject.PARAM_CONSTRUCT))

    def __init__(self, layout):
        Gtk.CellRenderer.__init__(self)
        self.layout = layout

    def do_get_size(self, widget, cell_area=None):
        height = 20
        max_width = 100
        if cell_area:
            return (cell_area.x, cell_area.y,
                    max(cell_area.width, max_width), cell_area.height)
        return (0, 0, max_width, height)

    def do_render(self, cr, widget, bg_area, cell_area, flags):
        context = widget.get_style_context()
        context.save()
        context.add_class(Gtk.STYLE_CLASS_BUTTON)
        self.layout.set_markup("Install")
        (x, y, w, h) = self.do_get_size(widget, cell_area)
        h -= 4
        # Gtk.render_background(context, cr, x, y, w, h)
        Gtk.render_frame(context, cr, x, y, w-2, h+4)
        Gtk.render_layout(context, cr, x + 10, y, self.layout)
        context.restore()
