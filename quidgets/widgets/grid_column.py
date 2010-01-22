# -*- coding: utf-8 -*-
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
    """GridFilter: A widget that provides a user interface for filtering a
    treeview. A GridFilter hosts one ore more GridRows, which in turn host
    an active filter.

    """
    column_type = gobject.TYPE_STRING
    __sort_order = None
    default_filter = grid_filter.StringFilterCombo
    def __init__(self, key, index, dictionary_index, editable=True, format_function = None ):
        """Create a GridFilter for filtering an associated treeview.
        This class is used by BugsPane.

        arguments:
        headings -- a tuple of lists of column headers associated with the 
        treeview. Each list includes a string for the column title, a constructor
        for a widget that supports filtering (such as StringFilter or NumericFilter)
        and a zero-based position index for the specific column in the treeview that
        will position the header. 
        treeview -- the treeview to be filtered. 

        """
        self.index = index
        self.key = key
        self.list_store = None
        self.dictionary_index = dictionary_index
        self.initialize_renderer(editable, index)
        
        gtk.TreeViewColumn.__init__( self, key, self.renderer, text=index)
        if format_function is not None:
            self.set_cell_data_func(self.renderer, self.on_format, format_function)

        self.set_clickable(True)
        self.connect('clicked', self.sort_rows)
        self.set_resizable(True)

    def sort_rows(self, widget):
        sort_order = widget.get_sort_order()                
        
        rows = [tuple(r) + (i,) for i, r in enumerate(self.list_store)]
        if sort_order == gtk.SORT_ASCENDING:
            sort_order = gtk.SORT_DESCENDING

        else:
            sort_order = gtk.SORT_ASCENDING

        self.set_sort_indicator(True)
        self.set_sort_order(sort_order)
        
        if sort_order == gtk.SORT_ASCENDING:
            rows.sort(self.sort_ascending)
        else:
            rows.sort(self.sort_descending)

        self.list_store.reorder([r[-1] for r in rows])


    def sort_ascending(self, x, y):
        x = x[self.index]
        y = y[self.index]
        if x > y:
            return 1
        elif x == y:
            return 0
        elif x < y:
            return -1
       
    def sort_descending(self, x, y):
        x = x[self.index]
        y = y[self.index]
        if x > y:
            return -1
        elif x == y:
            return 0
        elif x < y:
            return 1
       


    def on_format(self,column, cell_renderer, tree_model, iter, format_function):
        string = format_function(tree_model.get_value(iter, self.index), cell_renderer)
        if string != None:
            cell_renderer.set_property('text', string)
    
    def initialize_renderer( self, editable, index ):
        self.renderer = gtk.CellRendererText()
        self.renderer.mode = gtk.CELL_RENDERER_MODE_EDITABLE
        self.renderer.set_property("editable", editable)
        self.renderer.connect("edited", self.cell_edited)
  
    def cell_edited(self, cellrenderertext, path, new_text, data=None):
        """ __edited - internal signal handler.
        Updates the dictionary if a cell in the Treeview
        has been edited.

        """

        #get an iterator that points to the edited row
        if self.list_store is not None:
            iter = self.list_store.get_iter(path)
            #update the ListStore with the new text
            self.list_store.set_value(iter, self.index, self.display_val(new_text))
        
            dictionary = self.list_store.get_value(iter,self.dictionary_index)
            dictionary[self.key] = self.real_val(new_text)

    def display_val(self, val):
        if val == None:
            return self.default_val()
        else:
            return str(val)

    def real_val(self, val):
            return self.display_val(val)

    def default_display_val(self):
        return ""

class CurrencyColumn( StringColumn ):
    """GridFilter: A widget that provides a user interface for filtering a
    treeview. A GridFilter hosts one ore more GridRows, which in turn host
    an active filter.

    """
    column_type = gobject.TYPE_STRING
    default_filter = grid_filter.NumericFilterCombo
    def __init__(self, key, index,dictionary_index, editable=True ):
        """Create a GridFilter for filtering an associated treeview.
        This class is used by BugsPane.

        arguments:
        headings -- a tuple of lists of column headers associated with the 
        treeview. Each list includes a string for the column title, a constructor
        for a widget that supports filtering (such as StringFilter or NumericFilter)
        and a zero-based position index for the specific column in the treeview that
        will position the header. 
        treeview -- the treeview to be filtered. 

        """

        StringColumn.__init__( self, key, index, dictionary_index, editable, self.currency_format)

    def initialize_renderer( self, editable, index ):
        self.renderer = gtk.CellRendererSpin()
        adj = gtk.Adjustment(0,-10000000000,10000000000,1)
        self.renderer.set_property("adjustment", adj)
        self.renderer.set_property("editable", editable)
        self.renderer.set_property("digits",2)
        self.renderer.connect("edited", self.cell_edited)

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
        try:
            return str(float(val))
        except:
            return ""

    def real_val(self, val):
        try:
            return float(val)
        except:
            return 0.0

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

        x = float(x)
        y = float(y)
        if x > y:
            return 1
        elif x == y:
            return 0
        elif x < y:
            return -1

    def sort_descending(self, x, y):
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

    def currency_format(self, val, cell_renderer):
        try:
            return "%.2f" % float(val)
        except:
            return ""

class TagsColumn( StringColumn ):
    column_type = gobject.TYPE_STRING
    default_filter = grid_filter.TagsFilterCombo


class IntegerColumn( StringColumn ):
    column_type = gobject.TYPE_STRING
    default_filter = grid_filter.NumericFilterCombo

    def __init__(self, key, index, dictionary_index, editable=True ):
        """Create a GridFilter for filtering an associated treeview.
        This class is used by BugsPane.

        arguments:
        headings -- a tuple of lists of column headers associated with the 
        treeview. Each list includes a string for the column title, a constructor
        for a widget that supports filtering (such as StringFilter or NumericFilter)
        and a zero-based position index for the specific column in the treeview that
        will position the header. 
        treeview -- the treeview to be filtered. 

        """
        StringColumn.__init__( self, key, index, dictionary_index, editable)

    def initialize_renderer( self, editable, index ):
        self.renderer = gtk.CellRendererSpin()
        adj = gtk.Adjustment(0,-10000000000,10000000000,1)
        self.renderer.set_property("adjustment", adj)
        self.renderer.set_property("editable", editable)
        self.renderer.connect("edited", self.cell_edited)

    def cell_edited(self, cellrenderertext, path, new_text, data=None):
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
        try:
            return str(int(val))
        except:
            return ""

    def real_val(self, val):
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

    def sort_descending(self, x, y):
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
    """GridFilter: A widget that provides a user interface for filtering a
    treeview. A GridFilter hosts one ore more GridRows, which in turn host
    an active filter.

    """

    column_type = gobject.TYPE_INT
    default_filter = grid_filter.CheckFilterCombo

    def __init__(self, key, index, dictionary_index, editable=True, format_function = None ):
        self.index = index
        self.key = key
        self.initialize_renderer(editable, index)
        self.list_store = None
        self.dictionary_index = dictionary_index

        gtk.TreeViewColumn.__init__( self, key, self.renderer)

        self.set_clickable(True)
        self.connect('clicked', self.sort_rows)
        self.set_cell_data_func(self.renderer, self.on_format)
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
            rows.sort(self.sort_ascending)
        else:
            rows.sort(self.sort_descending)

        self.list_store.reorder([r[-1] for r in rows])

    def sort_ascending(self, x, y):
        x = x[self.index]
        y = y[self.index]
        return y - x

    def sort_descending(self, x, y):
        x = x[self.index]
        y = y[self.index]
        return x - y

    def on_format(self,column, cell_renderer, tree_model, iter):
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
    
    def initialize_renderer( self, editable, index ):
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
        """use conventions to infer the boolean value to use when the value
        is not a boolean type.
    
        """
        if type(val) is type(True):
            if val:
                return 1
            else:
                return 0
        elif type(val) is type("a"):
            if val.lower() == "yes":
                return 1
            else:
                return 0
        else:
            return bool(val)

    def default_display_val(self):
        return -1


    def real_val(self, val):
        """use conventions to infer the boolean value to use when the value
        is not a boolean type.
    
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
