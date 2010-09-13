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
"""Specializations of Gtk.TreeViewColumns designer to work with
DictionaryGrid and descendants.

Using
Grid columns are not normally created directly, but rather created
automatically when a DictionaryGrid displays it's data. See the
DictionaryGrid documentation for how to use type hints and conventions
to control the type of column used for a key in a dictionary.

Customizing
The column types in this module are all descendants of gtk.TreeView, so
you can use all of the gtk.TreeView methods and properties to control
how a grid column looks or works.

#Find a grid column and change the title
for c in my_dictionary_grid.get_columns():
    if c.key = my_key:
        c.set_title("New Title")

Extending
To display data in a column with a string, such as to display words and
numbers, you should extend StringColumn. Otherwise, extend gtk.TreeView
directly. In either case, you will need to implement a set of functions.

A Grid Column must track two different data, a "real" value, which is tracked
in the dictionary for the row, and the "display" value, which is used
to determine a value to display to users. For example, CheckColumn stores
a real value of True, False, or None, but a display value of -1, 0, or 1,
and uses the display value to set the checkbox in it's CellRenderer.

Every new column must have the following function to support real
and display values:

display_val(self, val) - takes a real value and returns the cooresponding
display value

real_val(self, val) - takes a display value and returns the cooresponding
real value

default_display_val(self) - reutrn the value to display in the case where
a row does not contain a key, value pair for the specified column. For example
StringColumn returns an empty string ("")

A new column type will often require a specially configured gtk.CellRenderer.
If you are deriving from StringColumn, but are using a custom renderer,
you need to override the _initialize_renderer method, and set the
columns renderer property to the renderer. You should also connect the
CellRenderer's edit signal to a function that will update the underlying
dictionary when the cell is edited.


For instance, a CurrencyColumn has the following implemention for
_initialize_renderer:

    def _initialize_renderer( self, editable, index ):
        self.renderer = gtk.CellRendererSpin()
        adj = gtk.Adjustment(0,-10000000000,10000000000,1)
        self.renderer.set_property("adjustment", adj)
        self.renderer.set_property("editable", editable)
        self.renderer.set_property("digits",2)
        self.renderer.connect("edited", self._cell_edited)

You also need to define two class variable:
1. column_type, the gobject type for the column's display value.
This is needed so that the DictionaryGrid can create a ListStore

2. default_filter, the grid_filter type to use in cases where a
GridFilter is associate with the column.

For example, CurrencyColumn defines the following class variables:
column_type = gobject.TYPE_STRING
default_filter = grid_filter.NumericFilterCombo

"""



import sys
try:
    import pygtk
    pygtk.require("2.0")
    import gtk
    import gobject
    import grid_filter

except Exception, inst:
    print "some dependencies for GridFilter are not available"
    raise inst

        


class StringColumn( gtk.TreeViewColumn ):
    """StringColumn - Displays strings and tracks data as string.
    Uses a CellRendererText for display and editing. Not typically created
    directly in code, but rather created by a DictionaryGrid or descendant.

    Suitable as a base class for any column that needs to display a string.

    """

    column_type = gobject.TYPE_STRING
    __sort_order = None
    default_filter = grid_filter.StringFilterCombo
    def __init__(self, key, index, dictionary_index, editable=True, format_function = None ):
        """Creates a StringColumn

        Arguments:
        key - the key from the dict for the row. Also used as the title for the
        column by default.

        index - the position of the column in the grid.

        dictionary_index - the index in the ListStore where the dictionary
        for the row is stored. Typically len(dict).

        editable - False if the column does not allow the user to edit the
        values in the column. Defaults to True.

        format_function - and optional function to handle formatting of
        of the string to display. Defaults to None.

        """

        self.index = index
        self.key = key
        self.list_store = None
        self.dictionary_index = dictionary_index
        self._initialize_renderer(editable, index)

        gtk.TreeViewColumn.__init__( self, key, self.renderer, text=index)
        if format_function is not None:
            self.set_cell_data_func(self.renderer, self._on_format, format_function)

        self.set_clickable(True)
        self.connect('clicked', self.sort_rows)
        self.set_resizable(True)

    def sort_rows(self, widget):
        """sort_rows - when called, the DictionaryGrid will resort
        from this column. The state of the sort button in the header
        will determine the sort order.

        """

        sort_order = widget.get_sort_order()

        rows = [tuple(r) + (i,) for i, r in enumerate(self.list_store)]
        if sort_order == gtk.SORT_ASCENDING:
            sort_order = gtk.SORT_DESCENDING

        else:
            sort_order = gtk.SORT_ASCENDING

        self.set_sort_indicator(True)
        self.set_sort_order(sort_order)

        if sort_order == gtk.SORT_ASCENDING:
            rows.sort(self._sort_ascending)
        else:
            rows.sort(self._sort_descending)

        self.list_store.reorder([r[-1] for r in rows])


    def _sort_ascending(self, x, y):
        """_sort_ascending - internal sort function that sorts two values
        in the column from least value to greatest value.

        returns 1 if x > y, 0 if x = y, -1 if x < y

        arguments:
        x - the value being compared to
        y - the value being compared

        """

        x = x[self.index]
        y = y[self.index]
        if x > y:
            return 1
        elif x == y:
            return 0
        elif x < y:
            return -1

    def _sort_descending(self, x, y):
        """_sort_descending - internal sort function that sorts two values
        in the column from greatest value to least value. May need to be
        implimented or overriden in specialized columns.

        returns 1 if x < y, 0 if x = y, -1 if x > y

        arguments:
        x - the value being compared to
        y - the value being compared

        """
        x = x[self.index]
        y = y[self.index]
        if x > y:
            return -1
        elif x == y:
            return 0
        elif x < y:
            return 1

    def _on_format(self,column, cell_renderer, tree_model, iter, format_function):
        """on format - internal signal handler called when the column needs
        to reformat the display value. Typically called after editing or when
        a value is first inserted.

        arguments:
        column - the index of the column, not typically needed

        cell_renderer - a reference to the specific cell_renderer that is
        formatting the string

        tree_model - the gtk.ListStore that is the backing data for the
        DictionaryGrid that contains the column.

        iter - an iterator that references the row of the the DictionaryGrid
        containing the cell that needs to be formatted.

        format_function - a function that takes the string and performs the
        actual formatting.

        """

        string = format_function(tree_model.get_value(iter, self.index), cell_renderer)
        if string != None:
            cell_renderer.set_property('text', string)

    def _initialize_renderer( self, editable, index ):
        """_initialize_renderer - internal function called to set up the
        CellRenderer for the column.

        arguments:

        editable - True if the column should support user editing.

        index - the position of the column in the grid

        """

        self.renderer = gtk.CellRendererText()
        self.renderer.mode = gtk.CELL_RENDERER_MODE_EDITABLE
        self.renderer.set_property("editable", editable)
        self.renderer.connect("edited", self._cell_edited)

    def _cell_edited(self, cellrenderertext, path, new_text, data=None):
        """ _cell_edited - internal signal handler called when a
        cell in the column is edited.

        arguments:

        cellrenderertext - the CellRenderer that was edited

        path - path to the row in the treeview

        new_text - the text was in the cell after the editing

        """

        #get an iterator that points to the edited row
        if self.list_store is not None:
            iter = self.list_store.get_iter(path)
            #update the ListStore with the new text
            self.list_store.set_value(iter, self.index, self.display_val(new_text))

            dictionary = self.list_store.get_value(iter,self.dictionary_index)
            dictionary[self.key] = self.real_val(new_text)

    def display_val(self, val):
        """display_val - takes a real value and returns the cooresponding
        display value

        arguments:

        val - the real value to convert

        """

        if val == None:
            return self.default_display_val()
        else:
            return str(val)

    def real_val(self, val):
        """real_val - takes a display value and returns the cooresponding
        real value.

        arguments:

        val - the display value to convert

        """

        #in a StringColumn, the backing data and the display data are the same
        return self.display_val(val)

    def default_display_val(self):
        """default_dislay_val - return the value to display in the case
        where there is no real value for the column for the row.

        """

        #display an empty string if there is no string for the cell
        return ""

class CurrencyColumn( StringColumn ):
    """CurrencyColumn - display data in currency format. Uses a gtk.Spinner
    to display data and support editing if enabled. Store real values as float.

    Inherits from StringColumn.

    """

    column_type = gobject.TYPE_STRING
    default_filter = grid_filter.NumericFilterCombo
    def __init__(self, key, index,dictionary_index, editable=True ):
        """Creates a CurrencyColumn

        Arguments:
        key - the key from the dict for the row. Also used as the title for the
        column by default.

        index - the position of the column in the grid.

        dictionary_index - the index in the ListStore where the dictionary
        for the row is stored. Typically len(dict).

        editable - False if the column does not allow the user to edit the
        values in the column. Defaults to True.

        """

        StringColumn.__init__( self, key, index, dictionary_index, editable, self._currency_format)

    def _initialize_renderer( self, editable, index ):
        """_initialize_renderer - internal function called to set up the
        CellRenderer for the column.

        arguments:

        editable - True if the column should support user editing.

        index - the position of the column in the grid

        """

        self.renderer = gtk.CellRendererSpin()
        adj = gtk.Adjustment(0,-10000000000,10000000000,1)
        self.renderer.set_property("adjustment", adj)
        self.renderer.set_property("editable", editable)
        self.renderer.set_property("digits",2)
        self.renderer.connect("edited", self._cell_edited)

        #make sure the value was edited to something that can be
        #turned into an int
        try:
            float(new_text)
        except:
            return

        #get an iterator that points to the edited row
        if self.list_store is not None:

            iter = self.list_store.get_iter(path)
            #update the ListStore with the new text
            self.list_store.set_value(iter, self.index, self.display_val(new_text))
            dictionary = self.list_store.get_value(iter,self.dictionary_index)
            dictionary[self.key] = self.real_val(new_text)


    def display_val(self, val):
        """display_val - takes a real value and returns the cooresponding
        display value

        arguments:

        val - the real value to convert

        """

        try:
            return str(float(val))
        except:
            return ""        """Creates a CurrencyColumn

        Arguments:
        key - the key from the dict for the row. Also used as the title for the
        column by default.

        index - the position of the column in the grid.

        dictionary_index - the index in the ListStore where the dictionary
        for the row is stored. Typically len(dict).

        editable - False if the column does not allow the user to edit the
        values in the column. Defaults to True.

        """


    def real_val(self, val):
        """real_val - takes a display value and returns the cooresponding
        real value.

        arguments:

        val - the display value to convert

        """

        try:
            return float(val)
        except:
            return 0.0

    def default_display_val(self):
        """default_dislay_val - return the value to display in the case
        where there is no real value for the column for the row.

        """

        return ""

    def _sort_ascending(self, x, y):
        x = x[self.index]
        y = y[self.index]
        if x == "" and y == "":
            return 0
        if x == "" and y != "":
            return -1
        if x != "" and y == "":
            return 1

        x = float(x)
        y = float(y)
        if x > y:
            return 1
        elif x == y:
            return 0
        elif x < y:
            return -1

    def _sort_descending(self, x, y):
        x = x[self.index]
        y = y[self.index]
        if x == "" and y == "":
            return 0
        if x == "" and y != "":
            return 1
        if x != "" and y == "":
            return -1

        x = float(x)
        y = float(y)
        if x > y:
            return -1
        elif x == y:
            return 0
        elif x < y:
            return 1

    def _currency_format(self, val, cell_renderer):
        try:
            return "%.2f" % float(val)
        except:
            return ""

class TagsColumn( StringColumn ):
    """TagsColumn - A specialization of a StringColumn that differs
    only in that it uses a TagsFilterCombo for filtering in any
    attached GridFilter.

    """

    column_type = gobject.TYPE_STRING
    default_filter = grid_filter.TagsFilterCombo


class IntegerColumn( StringColumn ):
    """IntegerColumn - display data in Integer format. Uses a gtk.Spinner
    to display data and support editing if enabled. Store real values as int.

    Inherits from StringColumn.

    """

    column_type = gobject.TYPE_STRING
    default_filter = grid_filter.NumericFilterCombo

    def __init__(self, key, index, dictionary_index, editable=True ):
        """Creates an IntegerColumn

        Arguments:
        key - the key from the dict for the row. Also used as the title for the
        column by default.

        index - the position of the column in the grid.

        dictionary_index - the index in the ListStore where the dictionary
        for the row is stored. Typically len(dict).

        editable - False if the column does not allow the user to edit the
        values in the column. Defaults to True.

        """

        StringColumn.__init__( self, key, index, dictionary_index, editable)

    def _initialize_renderer( self, editable, index ):
        self.renderer = gtk.CellRendererSpin()
        adj = gtk.Adjustment(0,-10000000000,10000000000,1)
        self.renderer.set_property("adjustment", adj)
        self.renderer.set_property("editable", editable)
        self.renderer.connect("edited", self._cell_edited)

    def _cell_edited(self, cellrenderertext, path, new_text, data=None):
        """ __edited - internal signal handler.
        Updates the dictionary if a cell in the Treeview
        has been edited.

        """

        #make sure the value was edited to something that can be
        #turned into an int
        try:
            int(new_text)
        except:
            return

        #get an iterator that points to the edited row
        if self.list_store is not None:

            iter = self.list_store.get_iter(path)
            #update the ListStore with the new text
            self.list_store.set_value(iter, self.index, self.display_val(new_text))
            dictionary = self.list_store.get_value(iter,self.dictionary_index)
            dictionary[self.key] = self.real_val(new_text)


    def display_val(self, val):
        """display_val - takes a real value and returns the cooresponding
        display value

        arguments:

        val - the real value to convert

        """

        try:
            return str(int(val))
        except:
            return ""

    def real_val(self, val):
        """real_val - takes a display value and returns the cooresponding
        real value.

        arguments:

        val - the display value to convert

        """

        try:
            return int(val)
        except:
            return 0


    def default_display_val(self):
        return ""

    def sort_ascending(self, x, y):
        x = x[self.index]
        y = y[self.index]
        if x == "" and y == "":
            return 0
        if x == "" and y != "":
            return -1
        if x != "" and y == "":
            return 1

        x = int(x)
        y = int(y)
        if x > y:
            return 1
        elif x == y:
            return 0
        elif x < y:
            return -1

    def _sort_descending(self, x, y):
        x = x[self.index]
        y = y[self.index]
        if x == "" and y == "":
            return 0
        if x == "" and y != "":
            return 1
        if x != "" and y == "":
            return -1

        x = int(x)
        y = int(y)
        if x > y:
            return -1
        elif x == y:
            return 0
        elif x < y:
            return 1


class CheckColumn( gtk.TreeViewColumn ):
    """CheckColumn - display data as checkboxes. Store real values as bool.

    Inherits from gtk.TreeViewColumn.

    """

    column_type = gobject.TYPE_INT
    default_filter = grid_filter.CheckFilterCombo

    def __init__(self, key, index, dictionary_index, editable=True, format_function = None ):
        """Creates a StringColumn

        Arguments:
        key - the key from the dict for the row. Also used as the title for the
        column by default.

        index - the position of the column in the grid.

        dictionary_index - the index in the ListStore where the dictionary
        for the row is stored. Typically len(dict).

        editable - False if the column does not allow the user to edit the
        values in the column. Defaults to True.

        format_function - and optional function to handle formatting of
        of the string to display. Defaults to None.

        """

        self.index = index
        self.key = key
        self._initialize_renderer(editable, index)
        self.list_store = None
        self.dictionary_index = dictionary_index

        gtk.TreeViewColumn.__init__( self, key, self.renderer)

        self.set_clickable(True)
        self.connect('clicked', self.sort_rows)
        self.set_cell_data_func(self.renderer, self._on_format)
        self.extra_format_function = format_function

        self.set_resizable(True)

    def sort_rows(self, widget):
        sort_order = widget.get_sort_order()

        rows = [tuple(r) + (i,) for i, r in enumerate(self.list_store)]
        if sort_order == gtk.SORT_ASCENDING:
            sort_order = gtk.SORT_DESCENDING

        else:
            sort_order = gtk.SORT_ASCENDING

        self.set_sort_order(sort_order)
        self.set_sort_indicator(True)

        if sort_order == gtk.SORT_ASCENDING:
            rows.sort(self._sort_ascending)
        else:
            rows.sort(self._sort_descending)

        self.list_store.reorder([r[-1] for r in rows])

    def _sort_ascending(self, x, y):
        x = x[self.index]
        y = y[self.index]
        return y - x

    def _sort_descending(self, x, y):
        x = x[self.index]
        y = y[self.index]
        return x - y

    def _on_format(self,column, cell_renderer, tree_model, iter):
        cell_val = tree_model.get_value(iter, self.index)
        cell_renderer.set_property('inconsistent', False)
        if  cell_val == 1:
            cell_renderer.set_active(True)
        elif cell_val == 0:
            cell_renderer.set_active(False)
        else:
            cell_renderer.set_property('inconsistent', True)
        #TODO: show it checked, unchecked, inconsistent ... based (-1,0,1)
        if self.extra_format_function != None:
            self.extra_format_function()

    def _initialize_renderer( self, editable, index ):
        self.renderer = gtk.CellRendererToggle()
        self.renderer.set_property("activatable", editable)
        col = gtk.TreeViewColumn(self.key, self.renderer, active=index)
        self.renderer.connect("toggled", self.toggled)

    def toggled(self, cell, path, data=None):
        #get an iterator that points to the edited row
        new_val = not cell.get_active()
        if self.list_store is not None:
            iter = self.list_store.get_iter(path)
            #update the ListStore with the new text
            self.list_store.set_value(iter, self.index, new_val)

            dictionary = self.list_store.get_value(iter,self.dictionary_index)
            dictionary[self.key] = new_val

    def display_val(self, val):
        """display_val - takes a real value and returns the cooresponding
        display value

        arguments:

        val - the real value to convert

        """

        if type(val) is bool:
            if val:
                return 1
            else:
                return 0
        elif type(val) is str:
            if val.lower() == "yes":
                return 1
            else:
                return 0
        elif type(val) is None:
            return self.default_display_val()
        else:
            return bool(val)

    def default_display_val(self):
        """default_dislay_val - return the value to display in the case
        where there is no real value for the column for the row.

        """

        return -1


    def real_val(self, val):
        """real_val - takes a display value and returns the cooresponding
        real value.

        arguments:

        val - the display value to convert

        """

        if type(val) is type(True):
            return val
        elif type(val) is type("a"):
            if val.lower() == "yes":
                return True
            else:
                return False
        else:
            return bool(val)


        
class ImageColumn (StringColumn):
    column_type = gtk.gdk.Pixbuf
    def __init__(self, key, index,dictionary_index, editable=False ):
        self.index = index
        self.key = key
        self.list_store = None
        self.dictionary_index = dictionary_index
        self._initialize_renderer(editable, index)

        gtk.TreeViewColumn.__init__( self, key, self.renderer, pixbuf=index)

        self.set_clickable(True)
        self.connect('clicked', self.sort_rows)
        self.set_resizable(True)
 
    def _initialize_renderer( self, editable, index ):
        self.renderer = gtk.CellRendererPixbuf()
