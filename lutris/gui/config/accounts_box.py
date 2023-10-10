from gettext import gettext as _

from gi.repository import Gtk

from lutris.gui.config.base_config_box import BaseConfigBox


class AccountsBox(BaseConfigBox):
    def __init__(self):
        super().__init__()
        self.add(self.get_section_label(_("Steam accounts")))
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        listbox = Gtk.ListBox(visible=True)
        frame.add(listbox)
        self.pack_start(frame, False, False, 12)
