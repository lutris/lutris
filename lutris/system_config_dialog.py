from lutris.config import LutrisConfig
from lutris.system_config_vbox import SystemConfigVBox
import gtk

class SystemConfigDialog(gtk.Dialog):
    def __init__(self):
        gtk.Dialog.__init__(self)
        self.set_title("System preferences")
        self.set_size_request(400,500)
        self.lutris_config = LutrisConfig()
        self.system_config_vbox = SystemConfigVBox(self.lutris_config,'system')
        self.vbox.pack_start(self.system_config_vbox)
        
        #Action area
        cancel_button = gtk.Button(None, gtk.STOCK_CANCEL)
        add_button = gtk.Button(None, gtk.STOCK_SAVE)
        self.action_area.pack_start(cancel_button)
        self.action_area.pack_start(add_button)
        cancel_button.connect("clicked", self.close)
        add_button.connect("clicked", self.save_config)
        
        self.show_all()

    def save_config(self,widget):
        print "config",self.system_config_vbox.lutris_config.config
        self.system_config_vbox.lutris_config.save()
        self.destroy()

    def close(self,widget):
        self.destroy()
        
