from gettext import gettext as _

from gi.repository import Gtk

from lutris.gui.installer.widgets import InstallerLabel
from lutris.util.strings import gtk_safe, gtk_safe_urls


class InstallerScriptBox(Gtk.Box):
    """Box displaying the details of a script, with associated action buttons"""

    def __init__(self, script, parent=None, revealed=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.script = script
        self.parent = parent
        self.revealer = None
        self.set_margin_start(12)
        self.set_margin_end(12)
        box = Gtk.Box(spacing=12, margin_top=6, margin_bottom=6)
        infobox = self.get_infobox()
        infobox.set_hexpand(True)
        box.append(infobox)
        box.append(self.get_install_button())
        self.append(box)
        self.append(self.get_revealer(revealed))

    def get_rating(self):
        """Return a string representation of the API rating"""
        return ""

    def get_infobox(self):
        """Return the central information box"""
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        runner_label = InstallerLabel("%s" % self.script["runner"])
        runner_label.add_css_class("info-pill")
        title_box.append(runner_label)
        title_box.append(InstallerLabel("<b>%s</b>" % gtk_safe(self.script["version"]), selectable=True))
        spacer = InstallerLabel("")
        spacer.set_hexpand(True)
        title_box.append(spacer)
        rating_label = InstallerLabel(self.get_rating(), selectable=True)
        rating_label.set_xalign(1)
        title_box.append(rating_label)
        info_box.append(title_box)
        info_box.append(self.get_credits())
        info_box.append(InstallerLabel(gtk_safe_urls(self.script["description"]), selectable=True))

        return info_box

    def get_revealer(self, revealed):
        """Return the revelaer widget"""
        self.revealer = Gtk.Revealer()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True)
        box.append(self.get_notes())

        self.revealer.set_child(box)
        self.revealer.set_reveal_child(revealed)
        return self.revealer

    def get_install_button(self):
        """Return the install button widget"""
        install_button = Gtk.Button(label=_("Install"))
        install_button.set_valign(Gtk.Align.START)
        install_button.connect("clicked", self.on_install_clicked)
        install_button.add_css_class("suggested-action")
        return install_button

    def get_notes(self):
        """Return the notes widget"""
        notes = self.script["notes"].strip()
        if not notes:
            return Gtk.Box()
        return self._get_installer_label(notes)

    def get_credits(self):
        credits_text = self.script.get("credits", "").strip()
        if not credits_text:
            return Gtk.Box()
        return self._get_installer_label(gtk_safe_urls(credits_text))

    def _get_installer_label(self, text):
        _label = InstallerLabel(text, selectable=True)
        _label.set_margin_top(12)
        _label.set_margin_bottom(12)
        _label.set_margin_end(12)
        _label.set_margin_start(12)
        return _label

    def reveal(self, reveal=True):
        """Show or hide the information in the revealer"""
        if self.revealer:
            self.revealer.set_reveal_child(reveal)

    def on_install_clicked(self, _widget):
        """Handler to notify the parent of the selected installer"""
        self.parent.emit("installer-selected", self.script["version"])
