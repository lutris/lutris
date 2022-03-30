from gettext import gettext as _

from gi.repository import Gtk

from lutris.gui.installer.widgets import InstallerLabel
from lutris.util.strings import add_url_tags, gtk_safe


class InstallerScriptBox(Gtk.VBox):
    """Box displaying the details of a script, with associated action buttons"""

    def __init__(self, script, parent=None, revealed=False):
        super().__init__()
        self.script = script
        self.parent = parent
        self.revealer = None
        self.set_margin_left(12)
        self.set_margin_right(12)
        box = Gtk.Box(spacing=12, margin_top=6, margin_bottom=6)
        box.pack_start(self.get_infobox(), True, True, 0)
        box.add(self.get_install_button())
        self.add(box)
        self.add(self.get_revealer(revealed))

    def get_rating(self):
        """Return a string representation of the API rating"""
        return ""

    def get_infobox(self):
        """Return the central information box"""
        info_box = Gtk.VBox(spacing=6)
        title_box = Gtk.HBox(spacing=6)
        runner_label = InstallerLabel("%s" % self.script["runner"])
        runner_label.get_style_context().add_class("info-pill")
        title_box.pack_start(runner_label, False, False, 0)
        title_box.add(InstallerLabel("<b>%s</b>" % gtk_safe(self.script["version"])))
        title_box.pack_start(InstallerLabel(""), True, True, 0)
        rating_label = InstallerLabel(self.get_rating())
        rating_label.set_alignment(1, 0.5)
        title_box.pack_end(rating_label, False, False, 0)
        info_box.add(title_box)
        info_box.add(self.get_credits())
        info_box.add(InstallerLabel(add_url_tags(self.script["description"])))

        return info_box

    def get_revealer(self, revealed):
        """Return the revelaer widget"""
        self.revealer = Gtk.Revealer()
        box = Gtk.VBox(visible=True)
        box.add(self.get_notes())

        self.revealer.add(box)
        self.revealer.set_reveal_child(revealed)
        return self.revealer

    def get_install_button(self):
        """Return the install button widget"""
        align = Gtk.Alignment()
        align.set(0, 0, 0, 0)

        install_button = Gtk.Button(_("Install"))
        install_button.connect("clicked", self.on_install_clicked)
        align.add(install_button)
        return align

    def get_notes(self):
        """Return the notes widget"""
        notes = self.script["notes"].strip()
        if not notes:
            return Gtk.Alignment()
        return self._get_installer_label(notes)

    def get_credits(self):
        credits_text = self.script.get("credits", "").strip()
        if not credits_text:
            return Gtk.Alignment()
        return self._get_installer_label(add_url_tags(credits_text))

    def _get_installer_label(self, text):
        _label = InstallerLabel(text)
        _label.set_margin_top(12)
        _label.set_margin_bottom(12)
        _label.set_margin_right(12)
        _label.set_margin_left(12)
        return _label

    def reveal(self, reveal=True):
        """Show or hide the information in the revealer"""
        if self.revealer:
            self.revealer.set_reveal_child(reveal)

    def on_install_clicked(self, _widget):
        """Handler to notify the parent of the selected installer"""
        self.parent.emit("installer-selected", self.script["version"])
