# -*- coding: utf-8 -*-
### BEGIN LICENSE
# Copyright (C) 2010 Rick Spencer rick.spencer@canonical.com
#This program is free software: you can redistribute it and/or modify it
#under the terms of the GNU General Public License version 3, as published
#by the Free Software Foundation.
#
#This program is distributed in the hope that it will be useful, but
#WITHOUT ANY WARRANTY; without even the implied warranties of
#MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
#PURPOSE.  See the GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License along
#with this program.  If not, see <http://www.gnu.org/licenses/>.
### END LICENSE
"""A gtk.TreeView for Dictionaries
Displays and persists data in a gtk.TreeView. Handles the
set up of the gtk.TreeView, gtk.ListModel, gtk.TreeViewColumns,
and gtk.CellRenderers.

Using
#create a dictionary if you don't already have one
dicts = [{"test?":True,"price":100,"foo count":100,"Key4":"1004"},
    {"test?":True,"price":100,"foo count":100,"Key4":"1004"},
    {"test?":True,"price":100,"foo count":100,"Key4":"1004"}]

#create the DictionaryGrid
dg = DictionaryGrid(dictionaries=dicts)

Configuring
#set UI to be editable
dg.editable = True

#Define columns to display
keys=["price","test?"]
dg = DictionaryGrid(dictionaries=dicts,keys=keys)

#Define column types to use
hints = {"price": StringColumn}
dg = CouchGrid(dictionaries=dicts,keys=keys, type_hints = hints)

#A CouchGrid is gtk.TreeView, so you can use gtk.TreeView members
dg.get_column(0).set_title("Price")

#Use the selection-changed signal and read from the DictionaryGrid
dg.connect("selection-changed", __handle_selection_changed)
def __handle_selection_changed(widget, dictionaries, data = None):
    for dictionary in dictionaries:
        print dictionary["price"]

#Use the cell-edited signal to track changes
dg.connect("cell-edited", __handle_edited_cells)
def __handle_edited_cells(widget, cell, row, key,  new_value, data=None):
    print new_value

Extending
To change what a DictionaryGrid does every time it builds itself
override DictionaryGrid._refresh_treeview. Here you can read data
form a data store, change the way the columns from
quickly.widgetsgrid_column are built, etc...

To change what a DictionaryGrid does every time a row of data is
add, override "append_row". Here you can change add data to store
with the dictionary being added, change the data itself, change
how the data is being displayed, etc...

"""

import gtk
import gobject
import conventions
from lutris.gui.grid_column import StringColumn, CheckColumn, ImageColumn

class DictionaryGrid(gtk.TreeView):
    def __init__(self, dictionaries=None, editable = False, keys=None, type_hints=None):
        """
        Creates a new DictionaryGrid
        arguments:

        dictionaries - a list of dictionaries to initialize in the
        grid.

        keys - a list of strings specifying keys to use in
        the columns of the DictionaryGrid.

        The types for the columns will be inferred by the key based on
        some conventions. the key "id" is assumed to be an integer, as
        is any key ending in " count". A key ending in "?" is assumed
        to be a Boolean displayed with a checkbox. The key "price" is
        assumed to be currency, as is any key ending in "count". There
        may be others. Defaults can be overridden using type-hints. All
        other keys will be assumed to be strings.

        type-hints - a dictionary containing keys specificed for the
        TreeView and GridColumns. Used to override types inferred
        by convention, or for changing the type of a column from
        the default of a string to something else.

        """

        gtk.TreeView.__init__(self)

        self.list_store = None
        self._keys = keys
        self._editable = editable
        if dictionaries is None:
            self._dictionaries = []
        else:
            self._dictionaries = dictionaries
        if type_hints is None:
            self._type_hints = {}
        else:
            self._type_hints = type_hints
        self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self._refresh_treeview()

        #signal handlers to track selection in the treeview
        #utlmiately these all emit the "selection_changed signal
        self.connect("cursor_changed", self.__selection_changed)
        self.connect("move-cursor", self.__cursor_moved)
        self.connect("select-all", self.__selection_all)
        self.connect("select-cursor-row", self.__selection_changed)
        self.connect("unselect-all", self.__selection_none)
        self.connect("toggle-cursor-row", self.__selection_changed)

    def __cursor_moved(self, grid, step, count, data=None):
        self.__selection_changed(self)

    def __selection_all(self, treeview, data=None):
        self.emit("selection-changed", self.rows)

    def __selection_none(self, treeview, data=None):
        self.emit("selection-changed", [])

    def __selection_changed(self, treeiew, data=None):
        self.emit("selection-changed", self.selected_rows)

    def __edited_toggled(self, cell, path, col):
        iter = self.list_store.get_iter(path)
        key = col.key
        active = not cell.get_active()
        self.__edited(cell, path, active, col)

    def __edited(self, cell, path, new_val, col):
        """ _edited - internal signal handler.
        Updates the database if a cell in the Treeview
        has been edited.

        """
        iter = self.list_store.get_iter(path)
        row_dict = self.get_model().get_value(iter,len(self.keys))
        key = col.key
        dictionary = self.list_store.get_value(iter,len(self.keys))
        self.emit("cell-edited",cell, path, key, new_val, row_dict)


    @property
    def keys(self):
        """ set keys - A list of strings to act as keys for the
        backing dictionaries and the default titles for the columns.

        Setting this property will cause the widget to reload.

        """

        return self._keys

    @keys.setter
    def keys(self, keys):
        self._keys = keys
        self._refresh_treeview()

    @property
    def editable(self):
        """editable - bool value, True to make editable

        Setting this property will cause the widget to reload.

        """
        return self._editable

    @editable.setter
    def editable(self, editable):
        self._editable = editable

        #refresh the treeview if possible
        self._refresh_treeview()

    def get_dictionaries_copy(self):
        """get_dictionaries_copy -returns a copy of the dictionaries in
        the dictionary grid.

        """
        return self._dictionaries[:]

    def _infer_keys_from_dictionaries(self):
        """_infer_keys_from_dictionaries: an internal function to
        set _keys suitable for column titles from a set of dictionaries.

        _infer_keys_from_dictionaries is not typically called directly,
        but may be useful to override in subclasses.

        """
        key_collector = []
        for r in self._dictionaries:
            for k in r.keys():
                if k not in key_collector and not k.startswith("__"):
                    key_collector.append(k)

        self.keys = key_collector

    def _refresh_treeview(self):
        """
        _refresh_treeview: internal function to handle rebuilding
        the gtk.TreeView along with columns and cell renderers..

        _refresh_treeview is not typically called directly,
        but may be useful to override in subclasses.

        """

        #if keys are already set, set up titles and columns
        if self.keys is not None:
            self.__reset_model()

        #if keys aren't set, infer them from the collection
        if len(self._dictionaries) > 0 and self.keys is None:
            self._infer_keys_from_dictionaries()
            self.__reset_model()

        for dictionary in self._dictionaries:
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
        print new_row
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
        """ __append_dict: internal function, do not call directly"""

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
        """
        remove_selected_rows: removes the rows currently selected
        in the TreeView UI from the TreeView as well as the backing
        gtk.ListStore.

        """

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
        This function is typically called when the TreeView needs
        to be rebuilt. Creates new columns.

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
            if k in self._type_hints:
                column = self._type_hints[k](k,i,len(self.keys))
            else:
                #no column supplied, use conventions to get a column
                column = conventions.get_column(k,i,len(self.keys), self.editable)

            #add the created column, and remember it's key
            self.append_column(column)
            self.__columns_map[k] = column

            #store the into for creating the list store
            col_types.append(column.column_type)

        #create the liststore with the designated types
        #the last column is always for storing the backing dict
        col_types.append(gobject.TYPE_PYOBJECT)
        print col_types
        self.list_store = gtk.ListStore(*col_types)

        for c in self.get_columns():
            self.__last_sorted_col = None
            c.list_store = self.list_store

            #TODO: store and delete these, this is a leak
            c.connect("clicked",self.__remove_sort_icon)

            #connect to the edit events to rip it a
            if type(c) == CheckColumn:
                c.renderer.connect("toggled",self.__edited_toggled, c)
            elif type(c) != ImageColumn:
                c.renderer.connect("edited",self.__edited, c)


    def __remove_sort_icon(self, column):
        """__remove_sort_icon: internal function used in handling
        display of sort buttons. Do not call this function directly.

       """

        if self.__last_sorted_col is not None:
            if self.__last_sorted_col is not column:
                self.__last_sorted_col.set_sort_indicator(False)
        self.__last_sorted_col = column

    __gsignals__ = {'cell-edited' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
        (gobject.TYPE_PYOBJECT,gobject.TYPE_PYOBJECT,gobject.TYPE_PYOBJECT,gobject.TYPE_PYOBJECT,gobject.TYPE_PYOBJECT)),

            'selection-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
            (gobject.TYPE_PYOBJECT,))
        }

def __show_selected(widget, selected_rows, data=None):
    """handles displaying text for test app"""

    tv.get_buffer().set_text(str(selected_rows))

def __on_edited(widget, cell, row, key,  new_value, row_dict, tv):
    """handles displaying text for test app"""

    string = "row: " + str(row)
    string += ", key: " + str(key)
    string += ", new value: " + str(new_value)
    string += "\n" + str(row_dict)
    tv.get_buffer().set_text(string)

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
    grid = DictionaryGrid(dicts, editable=True)#, ["ID","tags","price","bing count","key?"])

    #allow editing
    #grid.editable = True

    #show the control, add it to the window, and run the main loop
    grid.show()
    vbox.pack_start(grid, False, True)

    #create a test display area
    hbox = gtk.HBox(False, 5)
    hbox.show()
    tv = gtk.TextView()
    tv.show()
    grid.connect("selection-changed",__show_selected, tv)
    grid.connect("cell-edited",__on_edited, tv)

    hbox.pack_start(tv, False, False)
    vbox.pack_end(hbox, False, False)

    #run the test app
    gtk.main()

