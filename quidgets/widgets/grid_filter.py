# -*- coding: utf-8 -*-
import sys
try:
 import pygtk
 pygtk.require("2.0")
 import gtk
 import gobject

except Exception, inst:
 print "some dependencies for GridFilter are not available"
 raise inst

class GridFilter( gtk.VBox ):
 """GridFilter: A widget that provides a user interface for filtering a
 treeview. A GridFilter hosts one ore more GridRows, which in turn host
 an active filter.

 """
 def __init__(self, grid, filter_hints={} ):
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

  gtk.VBox.__init__( self, False, 10 )
  self.grid = grid
  self.store = grid.get_model()
  self.filter_hints = filter_hints

  #create the and/or radio buttons
  radio_box = gtk.HBox(False,2)
  radio_box.show()
  self.pack_start(radio_box, False, False)
  self.and_button = gtk.RadioButton(None,"M_atch All of the following", True)
  self.and_button.show()
  self.and_button.connect("toggled",self.__filter_changed)
  radio_box.pack_start(self.and_button, False, False)
  or_button = gtk.RadioButton(self.and_button,"Match any _of the following", True)
  or_button.show()
  radio_box.pack_start(or_button, False, False)
  self.rows = []
  self.add_row(self)

 def add_row(self, widget, data=None):
  """add_row: signal handler that receives a request from a FilterRow to
  add a new row. Sets up and adds the row to the GridFilter.

  """

  row = FilterRow(self.grid, len(self.rows) > 0, self.filter_hints )
  row.connect('add_row_requested',self.add_row)
  row.connect('remove_row_requested',self.remove_row)
  row.connect('refilter_requested',self.__filter_changed)
  row.show()
  self.rows.append(row)
  self.pack_start(row, False, False)
 
 def remove_row(self, widget, none):
  """remove_row: signal handler that receives a request from a FilterRow
  to remove itself from the GridFilter.

  """
  self.rows.remove(widget)
  self.remove(widget)
  self.__filter_changed(self)

 #TODO: call this and iterate through each filter row
 #create a signal handler for changes to filter in filter rows
 #from the handler call the filter_list function which ...
 #iterates through each row getting a true or false
 def __filter_changed(self,widget, data=None):
  """__filter_changed: signal handler that handles requests to reapply the
  fitlers in the GridFilter's FilterRows.

  """
  filt = self.store.filter_new()
  sort_mod = gtk.TreeModelSort(filt)
  filt.set_visible_func(self.__filter_func, data )
  filt.refilter()
  self.grid.set_model(sort_mod)
  
 def __filter_func(self, model, iter, data):
  """filter_func: called for each row in the treeview model in response to
  a __filter_changed signal. Determines for each row whether it should be
  visible based on the FilterRows in the GridFilter.

  """
  #determine whether this is an "and" or an "or" filter
  match_all = self.and_button.get_active()

  for r in self.rows:
   rez = r.is_match(iter.copy(),model)  #check the result of each filter
   if match_all:                        #if it's an "and" filter
    if not rez:                         #and if the filter does not match
     return False                       #then the row should not be visible
   else:                                #but if it's an "or" filter
    if rez:                             #and it is a match
     return True                        #return that the row should be visible
  return match_all  #all filters match an "and" or none matched an "or" 
  
class FilterRow( gtk.HBox):
 """FilterRow: A widget that displays a single filter in a GridFilter.
 Typically, this class will not be used directly, but only via a GridFilter.   
 
 """
 wait_for_input = False

 def __init__(self, grid, removable=True, filter_hints={}):
  """Create a FilterRow to be used in a GridFilter.
  A FitlerRow is comprised of a combo that lists the treeview headings.
  The combo stores the string to display for the heading, as well as
  the widget that is used to filter each heading. When the user changes
  the value in the dropdown, the FilterRow retrieves the correct filter from
  the combo, and displays that filter to the user.

  The FilterRow also handles offering UI for the user to add and remove
  FilterRows for the GridFilter containing it.
     
  arguments:
  headings -- a tuple of lists of column headers associated with the 
  treeview. Each list includes a string for the column title, a constructor
  for a widget that supports filtering (such as StringFilter or NumericFilter)
  and a zero-based position index for the specific column in the treeview that
  will position the header. 
  treeview -- the treeview to be filtered. 

  keyword arguments:
  removable -- bool if the row should be able to be removed from the GridFilter
               Typicall False for the first row.
  """
  gtk.HBox.__init__( self, False, 10 )
  self.store = grid.get_model()
  self.grid = grid

  heading_combo_store = gtk.ListStore(gobject.TYPE_STRING,gobject.TYPE_PYOBJECT,gobject.TYPE_INT)

  #apply default combos
  for i, k in enumerate(self.grid.keys):
   if k in filter_hints:
    filt_combo = filter_hints[k]
   else:
    filt_combo = grid.get_columns()[i].default_filter()
         
   heading_combo_store.append([k,filt_combo,i])

   filt_combo.connect("changed",self.__filter_changed)
   filt_combo.show()
 
  self.column_combo = gtk.ComboBox(heading_combo_store)
  cell = gtk.CellRendererText()
  self.column_combo.pack_start(cell, True)
  self.column_combo.add_attribute(cell, 'text', 0)

  self.filter_space = gtk.HBox(False,1)
  self.filter_space.show()

  self.filter_entry = gtk.Entry()
  self.filter_entry.show()
  self.filter_entry.connect("changed",self.__filter_changed)

  self.column_combo.show()
  self.pack_start(self.column_combo,False, False)
  self.column_combo.connect("changed",self.__column_changed)
  self.column_combo.set_active(0)

  self.pack_start(self.filter_space, False, False)
  self.pack_start(self.filter_entry, False)


  button_box = gtk.HBox(False,2)
  button_box.show()
  self.pack_start(button_box,False,False)

  #add a button that can create a new row in the grid filter
  add_button = gtk.Button(stock = gtk.STOCK_ADD)
  add_button.show()
  button_box.pack_start(add_button)
  add_button.connect("clicked",lambda x: self.emit('add_row_requested',self) )

  #add a button to remove the row if applicable
  if removable:
   rm_button = gtk.Button(stock = gtk.STOCK_REMOVE)
   rm_button.show()
   rm_button.connect('clicked', lambda x: self.emit("remove_row_requested",self) )
   button_box.pack_start(rm_button)

 __gsignals__ = {'add_row_requested' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
		(gobject.TYPE_PYOBJECT,)),
		'remove_row_requested' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
		(gobject.TYPE_PYOBJECT,)),
		'refilter_requested' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
		(gobject.TYPE_PYOBJECT,))
		}
 
 def __column_changed(self, widget, data = None):
  """column_changed: signal handler for the user changing the combo for the
  column that they wish to apply the filter to.
  removes the other filter widgets and replaces them widgets stored in
  the filter widget.

  """

  if len(self.filter_space.get_children()) > 0:
   self.filter_space.remove(self.filter_space.get_children()[0])   
  iter = widget.get_model().get_iter(widget.get_active())
  combo = widget.get_model().get_value(iter,1)
  print combo.requires_input
  if combo.requires_input:
   self.filter_entry.show()
   self.wait_for_input = True
  else:
   self.filter_entry.hide()
   self.wait_for_input = False
  self.filter_space.pack_start(combo, False, False)

 def __filter_changed(self,widget, data=None):
  """filter_changed: signal handler called when the FilterRow has changed.
  Used to tell the GridFilter to refilter. Only emits if the filter is 
  active (a heading is selected in the combo and the user has entered
  text in the filter.

  """
  
  if self.filter_entry.get_text() != "" or not self.wait_for_input:
   if self.__get_current_filter_combo().get_active > -1:
    self.emit('refilter_requested',self)

 def __get_current_filter_combo(self):
  """get_current_filter_combo: retrieves the combobox stored
  for the filter for the user selected treeview column.

  """
  iter = self.column_combo.get_model().get_iter(self.column_combo.get_active())
  return self.column_combo.get_model().get_value(iter,1)

 def is_match(self, store_iter, model):
  """is_match: returns true if the filter set in the FilterRow matches
  the value specified in the column and row. Used to determine whether 
  to hide or show a row.
  Typically called for each treeview row and each FilterRow in response
  to a change in one of the FilterRows.

  arguments:
  store_iter: the iter pointing the the row in the treeview to test
  model: the treeview model containing the rows being tested

  """
  #get the filter combo
  col_iter = self.column_combo.get_model().get_iter(self.column_combo.get_active())
  combo = self.column_combo.get_model().get_value(col_iter,1)

  #return if now combo is set
  if combo.get_active() < 0:
   return True

  #return if wating for input
  if self.wait_for_input and self.filter_entry.get_text() == "":
   return True
 

  #get the filter function from the selection in the fitler combo
  filt_iter = combo.get_model().get_iter(combo.get_active())
  filt_func = combo.get_model().get_value(filt_iter,1) 

  #find the column in the treeview to look in
  treeview_col = self.column_combo.get_model().get_value(col_iter,2)

  #pull the value out of the store
  orig_val = model.get_value(store_iter.copy(), treeview_col)
  if orig_val == None:
   orig_val = ""
  return filt_func(orig_val, self.filter_entry.get_text())    

class BlankFilterCombo( gtk.ComboBox):
 requires_input = True
 def __init__(self):
  """create a NumericFilterCombo

  """

  self.__combo_store = gtk.ListStore(gobject.TYPE_STRING,gobject.TYPE_PYOBJECT)
  gtk.ComboBox.__init__( self, self.__combo_store)
  cell = gtk.CellRendererText()
  self.pack_start(cell, True)
  self.add_attribute(cell, 'text', 0)

 def append(self, text, func):
    self.__combo_store.append([text, func])


class StringFilterCombo( BlankFilterCombo ):
 """StringFilterCombo: A default string filter class for use in a FilterRow.

    Lets the user specify if the row should be displayed based on
    containing, not containing, starting with, or ending with a user specified
    string.

    Stores a string describing how the filter will aapply, and a function
    for doing the actual filtering. The filter row currently manages a 
    text field for the user to enter strings.

    Currently, this manner of presenting a filter is hardcoded into FilterRow,
    so any custom Filters should work on the same manner.

 """
 def __init__(self):
  """create a StringFilterCombo.

  """
  BlankFilterCombo.__init__(self)
  self.append("contains",lambda x,y: x.find(y) > -1)
  self.append("does not contain",lambda x,y: x.find(y) == -1)
  self.append("starts with",lambda x,y: x.startswith(y))
  self.append("ends with",lambda x,y: x.endswith(y))

class TagsFilterCombo( BlankFilterCombo ):
 """TagsFilterCombo: A default tag filter class for use in a FilterRow.

    Lets the user specify if the row should be displayed based on
    containing a one tag or all tags.

    Stores a string describing how the filter will apply, and a function
    for doing the actual filtering. The filter row currently manages a 
    text field for the user to enter strings.

    Currently, this manner of presenting a filter is hardcoded into FilterRow,
    so any custom Filters should work on the same manner.

 """
 def __init__(self):
  BlankFilterCombo.__init__(self)

  def filter_any(bug_tags_s, filter_tags):
      tags_on_bug = bug_tags_s.split()
      tags_in_filter = filter_tags.split()

      for tag in tags_in_filter:
          if tag in tags_on_bug:
              return True
      return False

  def filter_all(bug_tags_s, filter_tags):
      tags_on_bug = bug_tags_s.split()
      tags_in_filter = filter_tags.split()

      for tag in tags_in_filter:
          if tag not in tags_on_bug:
              return False
      return True

  def filter_not(bug_tags_s, filter_tags):
      tags_on_bug = bug_tags_s.split()
      tags_in_filter = filter_tags.split()
              
      for tag in tags_in_filter:
          if tag not in tags_on_bug:
              return True
      return False

  def filter_not_all(bug_tags_s, filter_tags):
      tags_on_bug = bug_tags_s.split()
      tags_in_filter = filter_tags.split()

      for tag in tags_in_filter:
          if tag in tags_on_bug:
              return False
      return True
  
  self.append("has any of these tags", filter_any)
  self.append("has all of these tags", filter_all)
  self.append("does not have one of these tags", filter_not)
  self.append("does not have any of these tags", filter_not_all)

class CheckFilterCombo( BlankFilterCombo ):
 def __init__(self):
  """create a CheckFilterCombo

  """
  BlankFilterCombo.__init__( self )
  self.append("checked",lambda x,y: x == 1  )
  self.append("not Checked",lambda x,y: x ==0  )
  self.append("unset",lambda x,y: x == -1 )
  self.requires_input = False

class NumericFilterCombo( BlankFilterCombo ):
 """NumericFilterCombo: A default number filter class for use in a FilterRow.

    Lets the user specify if the row should be displayed based on numeric
    relationships to a number specified by the user.

    Stores a string describing how the filter will aapply, and a function
    for doing the actual filtering. The filter row currently manages a 
    text field for the user to enter numbers.

    Currently, this manner of presenting a filter is hardcoded into Filt
  print len(self.filter_hints)erRow,
    so any custom Filters should work on the same manner.

 """


 def __init__(self):
  """create a NumericFilterCombo

  """
  BlankFilterCombo.__init__( self )
  self.append("=",lambda x,y: float(x) == float(y) )
  self.append("<",lambda x,y: float(x) < float(y) )
  self.append(">",lambda x,y: float(x) > float(y) )
  self.append("<=",lambda x,y: float(x) <= float(y) )
  self.append(">=",lambda x,y:float(x) >= float(y) )


if __name__ == "__main__":
    """creates a test CouchGrid if called directly"""
    from dictionary_grid import DictionaryGrid

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
    dicts = [{"ID": 0, "key?": True, "tags": "aaa bbb ccc"},
                 {"ID": 1, "key?": False, "tags": "bbb ccc ddd"},
                 {"ID": 2, "key?": True, "tags": "ccc ddd eee"},
                 {"ID": 3, "key?": False, "tags": "ddd eee fff"},
                 {"ID": 4, "key?": True, "tags": "eee fff ggg"}]

    hints = {}
    grid = DictionaryGrid(dicts)
    grid.show()

    filt = GridFilter(grid,hints)
    filt.show()
    vbox.pack_start(filt, False, True)
    vbox.pack_end(grid, False, True)

    gtk.main()

