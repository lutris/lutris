"""Widgets for the installer window"""
from gi.repository import Gtk, GObject, Pango
from lutris.util.strings import escape_gtk_label
from lutris.gui.widgets.utils import get_icon


class InstallerLabel(Gtk.Label):
    """A label for installers"""
    def __init__(self, text):
        super().__init__()
        self.set_line_wrap(True)
        self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.set_alignment(0, 0.5)
        self.set_markup(escape_gtk_label(text))


class InstallerScriptBox(Gtk.VBox):
    """Box displaying the details of a script, with associated action buttons"""
    def __init__(self, script, parent=None):
        super().__init__()
        self.script = script
        self.parent = parent
        self.revealer = None

        box = Gtk.Box(spacing=12, margin_top=6, margin_bottom=6)
        box.add(self.get_icon())
        box.pack_start(self.get_infobox(), True, True, 0)
        box.add(self.get_install_button())
        self.add(box)
        self.add(self.get_revealer())

    def get_rating(self):
        """Return a string representation of the API rating"""
        try:
            rating = int(self.script["rating"])
        except (ValueError, TypeError, KeyError):
            return ""
        return "⭐" * rating

    def get_infobox(self):
        """Return the central information box"""
        info_box = Gtk.VBox(spacing=6)
        title_box = Gtk.HBox(spacing=6)
        title_box.add(InstallerLabel("<b>%s</b>" % self.script["version"]))
        title_box.pack_start(InstallerLabel(""), True, True, 0)
        rating_label = InstallerLabel(self.get_rating())
        rating_label.set_alignment(1, 0.5)
        title_box.pack_end(rating_label, False, False, 0)
        info_box.add(title_box)
        info_box.add(InstallerLabel("%s" % self.script["description"]))
        return info_box

    def get_revealer(self):
        """Return the revelaer widget"""
        self.revealer = Gtk.Revealer()
        self.revealer.add(self.get_notes())
        return self.revealer

    def get_icon(self):
        """Return the runner icon widget"""
        icon = get_icon(self.script["runner"], size=(32, 32))
        icon.set_margin_left(6)
        return icon

    def get_install_button(self):
        """Return the install button widget"""
        align = Gtk.Alignment()
        align.set(0, 0, 0, 0)

        install_button = Gtk.Button("Install")
        install_button.connect("clicked", self.on_install_clicked)
        install_button.set_margin_right(6)
        align.add(install_button)
        return align

    def get_notes(self):
        """Return the notes widget"""
        notes = self.script["notes"].strip()
        if not notes:
            return Gtk.Alignment()
        notes_label = InstallerLabel(notes)
        notes_label.set_margin_top(12)
        notes_label.set_margin_bottom(12)
        notes_label.set_margin_right(12)
        notes_label.set_margin_left(12)

        notes_scrolled_area = Gtk.ScrolledWindow()
        notes_scrolled_area.set_min_content_height(100)
        notes_scrolled_area.set_overlay_scrolling(False)
        notes_scrolled_area.add(notes_label)
        return notes_scrolled_area

    def reveal(self, reveal=True):
        """Show or hide the information in the revealer"""
        if self.revealer:
            self.revealer.set_reveal_child(reveal)

    def on_install_clicked(self, _widget):
        """Handler to notify the parent of the selected installer"""
        self.parent.emit("installer-selected", self.script["slug"])


class InstallerPicker(Gtk.ListBox):
    """List box to pick between several installers"""

    __gsignals__ = {"installer-selected": (GObject.SIGNAL_RUN_FIRST, None, (str, ))}

    def __init__(self, scripts):
        super().__init__()
        for script in scripts:
            self.add(InstallerScriptBox(script, parent=self))
        self.connect('row-selected', self.on_activate)
        self.show_all()

    def on_activate(self, widget, row):
        """Handler for hiding and showing the revealers in children"""
        for script_box_row in widget:
            script_box = script_box_row.get_children()[0]
            script_box.reveal(False)
        installer_row = row.get_children()[0]
        installer_row.reveal()
