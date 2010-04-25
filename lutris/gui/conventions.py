import gtk
import gobject
from grid_column import StringColumn, CurrencyColumn, CheckColumn
from grid_column import IntegerColumn, TagsColumn

def get_column(key, index, dictionary_index, editable):
    if key.lower() == "id":
        return IntegerColumn(key, index, dictionary_index, editable)
    elif key.endswith("?"):
        return CheckColumn(key, index, dictionary_index, editable)
    elif key.lower() == "price":
        return CurrencyColumn(key, index, dictionary_index, editable)
    elif key.lower() == "tags":
        return TagsColumn(key, index, dictionary_index, editable)
    elif key.lower().endswith(" count"):
        return IntegerColumn(key, index, dictionary_index, editable)
    else:
        return StringColumn(key, index, dictionary_index, editable)




