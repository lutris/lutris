# -*- coding: utf-8 -*-
### BEGIN LICENSE
# Copyright (C) 2010 Mathieu Comandon <strycore@gmail.com>
# This program is free software: you can redistribute it and/or modify it 
# under the terms of the GNU General Public License version 3, as published 
# by the Free Software Foundation.
# 
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranties of 
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR 
# PURPOSE.  See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along 
# with this program.  If not, see <http://www.gnu.org/licenses/>.
### END LICENSE
"""A Treeview for Dictionaries"""

import gtk
import gobject
from lutris.gui.conventions import *
from lutris.gui.grid_column import StringColumn

class DictionaryGrid(gtk.TreeView):
    def __init__(self, dictionaries=None, keys=None, type_hints=None):
        """Create a new Couchwidget
        arguments:
        dict - 
        keys

        """
        gtk.TreeView.__init__(self)
        self.list_store = None
        self.__keys = keys
        self.__editable = False
        if dictionaries == None:
            self.__dictionaries = []
        else:
            self.__dictionaries = dictionaries
        if type_hints == None:
            self.__type_hints={}
        else:
            self.__type_hints=type_hints
        #self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.__populate_treeview()

        self.connect("cursor_changed", self.__selection_changed)
        self.connect("move-cursor", self.__cursor_moved)
        self.connect("select-all", self.__selection_all)
        self.connect("select-cursor-row", self.__selection_changed)
        self.connect("unselect-all", self.__selection_none)
        self.connect("toggle-cursor-row", self.__selection_changed)

        #signal handlers to track selection in the treeview
        #utlmiately these all emit the "selection_changed signal
    def __cursor_moved(self, grid, step, count, data=None):
        self.__selection_changed(self)

    def __selection_all(self, treeview, data=None):
        self.emit("selection-changed", self.rows)

    def __selection_none(self, treeview, data=None):
        self.emit("selection-changed", [])

    def __selection_changed(self, treeview, data=None):
        self.emit("selection-changed", self.selected_rows)

    @property
    def keys(self):
        """ set keys - A list of strings to act as keys for the
        TreeView.

        Setting this property will cause the widget to reload.

        """

        return self.__keys

    @keys.setter
    def keys(self, keys):
        self.__keys = keys
        self.__populate_treeview()

    @property
    def editable(self):
        """editable - bool value, True to make editable
        If set to True, changes are immediately
        persisted to the database.

        """
        return self.__editable

    @editable.setter
    def editable(self, editable):
        self.__editable = editable

        #refresh the treeview if possible
        self.__populate_treeview()

    def get_dictionaries_copy(self):
        """returns a reference to the dictionaries in the
        dictionary grid. Note that 

        """
        return self.__dictionaries[:]

    def __populate_treeview(self):
        #if keys are already set, set up titles and columns
        if self.keys is not None:
            self.__reset_model()

        #if keys aren't set, infer them from the collection
        if len(self.__dictionaries) > 0 and self.keys is None:
            key_collector = []
            for r in self.__dictionaries:                
                for k in r.keys():
                    if k not in key_collector and not k.startswith("__"):
                        key_collector.append(k)
        
            self.keys = key_collector
            self.__reset_model()

        for dictionary in self.__dictionaries:          
            #lists have to match the list_store columns in length
            #so we have to make rows as long as the headerings
            #note that the last value is reserved for extra data
            self.append_row(dictionary)

        #apply the model to the Treeview if possible
        if self.list_store != None:
            self.set_model(self.list_store)

    def append_row(self, dictionary):
        """append_row: add a row to the TreeView. If keys are already set up
        only the the keys in the dictionary matching the keys used
        for columns will be used. If no keys are set up, and this is the
        first row, keys will be inferred from the dictionary keys.

        arguments:
        dictionary - a dictionary to the TreeView.

        """        
        new_row = []

        for i, k in enumerate(self.keys):
                if k in dictionary:
                    display_val = self.__columns_map[k].display_val(dictionary[k])
                    real_val = self.__columns_map[k].real_val(dictionary[k])
                    #TODO: store a "real_val" instead of display val
                    #that was "converted_val"
                    dictionary[k] = real_val
                else:
                    display_val = self.__columns_map[k].default_display_val()
                new_row.append(display_val)
        new_row.append(dictionary)
        self.list_store.append(new_row)

    @property
    def rows(self):
        """ rows - returns a list of dictionaries
        for each row in the grid.

        This property is read only.
        """
        model = self.get_model()
        rows = [] #list of rows to return
        model.foreach(self.__append_dict, rows)
        return rows

    def __append_dict(self, model, path, iter, rows):
        row = model.get_value(iter,len(self.keys))
        rows.append(row)

    @property
    def selected_rows(self):
        """ selected_rows - returns a list of dictionaries
        for each row selected. 

        This property is read only.
        """

        #get the selected rows in the ListStore
        selection = self.get_selection()
        model, model_rows = selection.get_selected_rows()
        
        rows = [] #list of rows to return

        for mr in model_rows:
            row = {} #a row to be added to the list of rows
            iter = model.get_iter(mr)

            row = model.get_value(iter,len(self.keys))
            rows.append(row)
        return rows

    def remove_selected_rows(self):
        #get the selected rows, and return if nothing is selected
        model, rows = self.get_selection().get_selected_rows()
        if len(rows) == 0:
            return

        #store the last selected row to reselect after removal
        next_to_select = rows[-1][0] + 1 - len(rows)
        
        #loop through and remove
        iters = [model.get_iter(path) for path in rows]
        for i in iters:
            self.get_model().remove(i)

        #select a row for the user, nicer that way
        rows_remaining = len(self.get_model()) 

        #don't try to select anything if there are no rows left        
        if rows_remaining < 1:
            return

        #select the next row down, unless it's out of range
        #in which case just select the last row
        if next_to_select < rows_remaining:
            self.get_selection().select_path(next_to_select)
        else:
            self.get_selection().select_path(rows_remaining - 1)


    def __reset_model(self):
        """ __reset_model - internal funciton, do not call directly.
        This function is typically called when properties are set

        """

        #remove the current columns from the TreeView
        cols = self.get_columns()
        for c in cols:
            self.remove_column(c)

        #reinitialize the column variables
        col_count = len(self.keys) + 1
        col_types = []
        self.__columns_map = {}

        #create a column for each key
        for i, k in enumerate(self.keys):
            #use any supllied columns
            if k in self.__type_hints:
                column = self.__type_hints[k](k,i,len(self.keys))
            else:
                #no column supplied, use conventions to get a column
                column = get_column(k,i,len(self.keys), self.editable)
                
            #add the created column, and remember it's key
            self.append_column(column)
            self.__columns_map[k] = column

            #store the into for creating the list store
            col_types.append(column.column_type)
            
        #create the liststore with the designated types
        #the last column is always for storing the backing dict
        col_types.append(gobject.TYPE_PYOBJECT)
        self.list_store = gtk.ListStore(*col_types)

        #now tell the columns what list_store to use if edited
        for c in self.get_columns():
            self.__last_sorted_col = None
            c.list_store = self.list_store
            c.connect("clicked",self.__remove_sort_icon)

    def __remove_sort_icon(self, column):
        if self.__last_sorted_col is not None:
            if self.__last_sorted_col is not column:
                self.__last_sorted_col.set_sort_indicator(False)
        self.__last_sorted_col = column

    __gsignals__ = {'selection-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
        (gobject.TYPE_PYOBJECT,)),
        }


def __show_selected(widget, selected_rows, data):
    tv, dg = data
    tv.get_buffer().set_text(str(selected_rows))

if __name__ == "__main__":
    """creates a test CouchGrid if called directly"""

    dicts = [{"key?": True, "price":0.00,"tags" : "aaa bbb ccc","_foo":"bar","bing count":20},
                 {"ID": 11, "key?": False, "price":2.00,"tags" : "bbb ccc ddd","_foo":"bar"},
                 {"key?": True, "price":33.00,"tags" : "ccc ddd eee","_foo":"bar","bing count":15},
                 {"ID": 3, "tags" : "ddd eee fff","_foo":"bar"},
                 {"ID": 4, "price":5.00,"_foo":"bar"}]
    #create and show a test window
    win = gtk.Window(gtk.WINDOW_TOPLEVEL)
    win.set_title("DictionaryGrid Test Window")
    win.connect("destroy",gtk.main_quit)
    win.show()

    #create a top level container
    vbox = gtk.VBox(False, False)
    vbox.show()
    win.add(vbox)

    #create a test widget with test database values
    grid = DictionaryGrid(dicts, ["ID","tags","price","bing count","key?"])

    #allow editing
    grid.editable = True

    #show the control, add it to the window, and run the main loop
    grid.show()
    vbox.pack_start(grid, False, True)

    #create a test display area
    hbox = gtk.HBox(False, 5)
    hbox.show()
    tv = gtk.TextView()
    tv.show()
    grid.connect("selection-changed",__show_selected, (tv,grid))

    hbox.pack_start(tv, False, False)
    vbox.pack_end(hbox, False, False)

    #run the test app
    gtk.main()

