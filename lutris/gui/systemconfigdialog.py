from gi.repository import Gtk

from lutris.config import LutrisConfig
from lutris.gui.systemconfigvbox import SystemConfigVBox


class SystemConfigDialog(Gtk.Dialog):
    def __init__(self):
        GObject.GObject.__init__(self)
        self.set_title("System preferences")
        self.set_size_request(400, 500)
        self.lutris_config = LutrisConfig()
        self.system_config_vbox = SystemConfigVBox(self.lutris_config,
                                                   'system')
        self.vbox.pack_start(self.system_config_vbox, True, True, 0)

        #Action area
        cancel_button = Gtk.Button(None, Gtk.STOCK_CANCEL)
        add_button = Gtk.Button(None, Gtk.STOCK_SAVE)
        self.action_area.pack_start(cancel_button, True, True, 0)
        self.action_area.pack_start(add_button, True, True, 0)
        cancel_button.connect("clicked", self.close)
        add_button.connect("clicked", self.save_config)

        self.show_all()

    def save_config(self, widget):
        # FIXME : Use logging system !
        print "config", self.system_config_vbox.lutris_config.config
        self.system_config_vbox.lutris_config.save()
        self.destroy()

    def close(self, widget):
        self.destroy()
