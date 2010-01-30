###############################################################################
## project
##
## Copyright (C) 2009 Mathieu Comandon strycore@gmail.com
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
###############################################################################

#Widget generators and their signal handlers

import gtk
import logging

class ConfigVBox(gtk.VBox):
    def __init__(self,save_in_key):
        gtk.VBox.__init__(self)
        self.options = None
        self.game_config = None # FIXME : remove this
        #Section of the configuration file to save options in. Can be "game", "runner" or "system"
        self.save_in_key= save_in_key

    def generate_widgets(self):
        for option in self.options:
            option_key = option["option"]
            if self.save_in_key in self.lutris_config.config:
                config = self.lutris_config.config[self.save_in_key]
            else:
                config = self.lutris_config.config[self.save_in_key] = {}
            if option_key in config:
                value = config[option_key]
            else:
                value = None
            if option["type"] == "one_choice":
                self.generate_combobox(option_key,option["choices"],option["label"],value)
            elif option["type"] == "bool":
                self.generate_checkbox(option_key,option["label"],value)
            elif option["type"] == "range":
                self.generate_range(option_key,option["min"], option["max"],option["label"],value)
            elif option["type"] == "string":
                self.generate_entry(option_key,option["label"],value)
            elif option["type"] == "directory_chooser":
                self.generate_directory_chooser(option_key,option["label"],value)
            elif option["type"] == "file_chooser" or option["type"] == "single":
                self.generate_file_chooser(option_key,option["label"],value)
            elif option["type"] == "multiple":
                self.generate_multiple_file_chooser(option_key, option["label"], value)
            else:
                print "WTF is %s ?" % option["type"]
    
    def generate_checkbox(self,option_name,label,value=None):
        checkbox = gtk.CheckButton(label)
        if value:
            checkbox.set_active(value)
        checkbox.connect("toggled",self.checkbox_toggle,option_name)
        checkbox.show()
        self.pack_start(checkbox,False,True,5)
    def checkbox_toggle(self,widget,option_name):
        self.lutris_config.config[self.save_in_key][option_name] = widget.get_active()

    def generate_entry(self,option_name,label,value=None):
        hbox = gtk.HBox()
        entry_label = gtk.Label(label)
        entry_label.set_size_request(200,30)
        entry = gtk.Entry()
        if value:
            entry.set_text(value)
        entry.connect("changed",self.entry_changed,option_name)
        hbox.pack_start(entry_label,False,False,5)
        hbox.pack_start(entry,True,True,5)
        hbox.show_all()
        self.pack_start(hbox,False,True,5)
    def entry_changed(self,entry,option_name):
        entry_text = entry.get_text()
        self.lutris_config.config[self.save_in_key][option_name] = entry_text

    def generate_combobox(self,option_name,choices,label,value=None):
        hbox = gtk.HBox()
        liststore = gtk.ListStore(str,str)
        for choice in choices:
            liststore.append(choice)
        combobox = gtk.ComboBox(liststore)
        combobox.set_size_request(200,30)
        cell = gtk.CellRendererText()
        combobox.pack_start(cell, True)
        combobox.add_attribute(cell, 'text', 0)  
        index = selected_index  = -1
        if value:
            for choice in choices:
                if choice[1] == value:
                    selected_index = index
                index = index +1 
        combobox.set_active(selected_index)
        combobox.connect('changed',self.on_combobox_change,option_name)
        gtklabel = gtk.Label(label)
        gtklabel.set_size_request(200,30)
        hbox.pack_start(gtklabel)
        hbox.pack_start(combobox)
        hbox.show_all()
        self.pack_start(hbox,False,True,5)
    def on_combobox_change(self,combobox,option):
        model = combobox.get_model()
        active = combobox.get_active()
        if active < 0:
            return None
        option_value = model[active][1]
        self.lutris_config.config[self.save_in_key][option] = option_value

    def generate_range(self,option_name,min,max,label,value=None):
        adjustment = gtk.Adjustment(float(min),float(min),float(max),1,0,0)
        spin_button = gtk.SpinButton(adjustment)
        if value:
            spin_button.set_value(value)
        spin_button.connect('changed',self.on_spin_button_changed,option_name)
        hbox = gtk.HBox()
        gtklabel = gtk.Label(label)
        gtklabel.set_size_request(200,30)
        hbox.pack_start(gtklabel)
        hbox.pack_start(spin_button)
        hbox.show_all()
        self.pack_start(hbox,False,True,5)
    def on_spin_button_changed(self,spin_button,option):
        value = spin_button.get_value_as_int()
        self.lutris_config.config[self.save_in_key][option] = value

    def generate_file_chooser(self,option_name,label,value=None):
        """Generates a file chooser button to choose a file"""
        logging.debug("File chooser")
        logging.debug(value)
        hbox = gtk.HBox()
        gtklabel = gtk.Label(label)
        gtklabel.set_size_request(200,30)
        file_chooser = gtk.FileChooserButton("Choose a file for %s" % label)
        file_chooser.set_size_request(200,30)

        file_chooser.set_action(gtk.FILE_CHOOSER_ACTION_OPEN)
        file_chooser.set_current_folder(self.lutris_config.get_path(self.runner_class))
        file_chooser.connect("file-set",self.on_chooser_file_set,option_name)
        if value:
            file_chooser.unselect_all()
            file_chooser.select_filename(value)
        hbox.pack_start(gtklabel,False,False,10)
        hbox.pack_start(file_chooser)
        self.pack_start(hbox,False,True,5)

    def generate_directory_chooser(self,option_name,label,value=None):
        """Generates a file chooser button to choose a directory"""
        hbox = gtk.HBox()
        gtklabel = gtk.Label(label)
        gtklabel.set_size_request(200,30)
        directory_chooser = gtk.FileChooserButton("Choose a directory for %s" % label)
        directory_chooser.set_size_request(200,30)
        directory_chooser.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
        if value:
            directory_chooser.set_current_folder(value)
        directory_chooser.connect("file-set",self.on_chooser_file_set,option_name)
        hbox.pack_start(gtklabel)
        hbox.pack_start(directory_chooser)
        self.pack_start(hbox,False,True,5)
        
    def on_chooser_file_set(self,filechooser_widget,option):
        directory =  filechooser_widget.get_filename()
        self.lutris_config.config[self.save_in_key][option] = directory
    
    def generate_multiple_file_chooser(self,option_name,label,value=None):
        hbox = gtk.HBox()
        gtk_label = gtk.Label(label)
        gtk_label.set_size_request(200,30)
        hbox.pack_start(gtk_label)
        self.files_chooser_dialog = gtk.FileChooserDialog(title="Select files",
                                                              parent=self.get_parent_window(),
                                                              action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                                              buttons=(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE,
                                                                       gtk.STOCK_ADD, gtk.RESPONSE_OK))
        self.files_chooser_dialog.set_select_multiple(True)
        self.files_chooser_dialog.connect('response', self.add_files_callback,option_name)

        files_chooser_button = gtk.FileChooserButton(self.files_chooser_dialog)
        files_chooser_button.set_current_folder(self.lutris_config.get_path(self.runner_class))
        if value:
            files_chooser_button.set_filename(value[0])
            
        hbox.pack_start(files_chooser_button)
        self.pack_start(hbox,False,True,5)
        if value:
            self.files = value
        else:
            self.files = []
        self.files_list_store = gtk.ListStore(str)
        for file in self.files:
            self.files_list_store.append([file])
        files_column = gtk.TreeViewColumn("Files")
        cell_renderer = gtk.CellRendererText()
        files_column.pack_start(cell_renderer)
        files_column.set_attributes(cell_renderer,text=0)
        files_treeview = gtk.TreeView(self.files_list_store)
        files_treeview.append_column(files_column)
        files_treeview.set_size_request(10,100)
        files_treeview.connect('key-press-event',self.on_files_treeview_event)
        treeview_scroll = gtk.ScrolledWindow()
        treeview_scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        treeview_scroll.add(files_treeview)
        self.pack_start(treeview_scroll,True,True)

        
    def generate_file_widget(self,widget_config,file_value=None):
        # FIXME : Remove me
        print "OLD CRAPPY FUNCTION CALLED (generate_file_widget)"
        widget_type = widget_config["type"]
        self.key_name_for_file = widget_config["name"]
        #lutris_config = LutrisConfig()
        if widget_type == "single":
            file_widget = gtk.HBox()
            file_label = gtk.Label(widget_config["label"])
            file_widget.pack_start(file_label,False,False,5)
            self.file_chooser_button = gtk.FileChooserButton("Select a file")
            self.file_chooser_button.connect("file-set",self.add_file_callback)
            self.file_chooser_button.set_current_folder(self.lutris_config.get_path(self.runner_class))
            if file_value:
                self.file_chooser_button.set_filename(file_value)
            #self.file_chooser_button.set_current_folder("/home/strider/Games/")
            file_widget.pack_start(self.file_chooser_button,True,True,5)

        self.pack_start(file_widget,False,False,10)

    def on_files_treeview_event(self,treeview,event):
        key =  event.keyval
        if key == gtk.keysyms.Delete:
            #TODO : Delete selected row
            print "you don't wanna delete this ... yet"
            
    def add_files_callback(self,dialog,response,option):
        """Add several files to the configuration"""
        if response == gtk.RESPONSE_OK:
            filenames = dialog.get_filenames()
            for filename in filenames:
                self.files_list_store.append([filename])
                if not filename in self.files:
                    self.files.append(filename)
        self.lutris_config.config[self.save_in_key][option] = self.files
        self.files_chooser_dialog = None
        
    def add_file_callback(self,widget,response=None):
        # FIXME : Remove me
        print "OLD CRAPPY FUNCTION CALLED (add_file_callback)"
        self.file = widget.get_filename()
        self.game_config["exe"]  = self.file
