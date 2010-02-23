import runners
import gtk
from lutris.runner_config_dialog import RunnerConfigDialog

class RunnersDialog(gtk.Dialog):
    """Dialog class  for the platform preferences"""

    def __init__(self):
        gtk.Dialog.__init__(self)
        self.set_title("Configure runners")
        self.set_size_request(450,400)
        
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.vbox.pack_start(scrolled_window,True,True,0)

        runner_list = runners.__all__
        runner_vbox = gtk.VBox()

        for runner in runner_list:
            hbox = gtk.HBox()
            #Label
            runner_instance = eval("runners."+runner+"."+runner+"()")
            machine = runner_instance.machine
            runner_label = gtk.Label()
            runner_label.set_markup("<b>"+runner + "</b> ( "+machine+" ) ")
            runner_label.set_width_chars(33)
            runner_label.set_line_wrap(True)
            hbox.pack_start(runner_label,True,True,5)
            #Button
            button_alignement = gtk.Alignment(xalign=0.0, yalign=0.0, xscale=0.5, yscale=0.0)
            if runner_instance.is_installed():
                button = gtk.Button("Configure")
                button.set_size_request(100,30)
                button.connect("clicked",self.on_configure_clicked,runner)
            else:
                button = gtk.Button("Install")
                button.set_size_request(100,30)
                button.connect("clicked",self.on_install_clicked,runner)
            button_alignement.add(button)
            hbox.pack_start(button_alignement,True,True)
            
            runner_vbox.pack_start(hbox,True,True,5)
        scrolled_window.add_with_viewport(runner_vbox)
        self.show_all()

    def close(self, widget=None, other=None):
        self.destroy()

    def on_install_clicked(self,widget,runner):
        runner_instance = eval("runners."+runner+"."+runner+"()")
        runner_instance.install_runner()

    def on_configure_clicked(self,widget,runner):
        RunnerConfigDialog(runner)

if __name__ == "__main__":
    dialog = RunnersDialog()
    gtk.main()
