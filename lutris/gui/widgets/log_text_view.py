# Third Party Libraries
from gi.repository import Gtk


class LogTextView(Gtk.TextView):  # pylint: disable=no-member

    def __init__(self, buffer=None, autoscroll=True):
        super().__init__()

        if buffer:
            self.set_buffer(buffer)
        self.set_editable(False)
        self.set_cursor_visible(False)
        self.set_monospace(True)
        self.set_left_margin(10)
        self.scroll_max = 0
        self.set_wrap_mode(Gtk.WrapMode.CHAR)
        self.get_style_context().add_class("lutris-logview")

        self.mark = self.create_new_mark(self.props.buffer.get_start_iter())

        if autoscroll:
            self.connect("size-allocate", self.autoscroll)

    def autoscroll(self, *args):  # pylint: disable=unused-argument
        adj = self.get_vadjustment()
        if adj.get_value() == self.scroll_max or self.scroll_max == 0:
            adj.set_value(adj.get_upper() - adj.get_page_size())
            self.scroll_max = adj.get_value()
        else:
            self.scroll_max = adj.get_upper() - adj.get_page_size()

    def create_new_mark(self, buffer_iter):
        return self.props.buffer.create_mark(None, buffer_iter, True)

    def reset_search(self):
        self.props.buffer.delete_mark(self.mark)
        self.mark = self.create_new_mark(self.props.buffer.get_start_iter())
        self.props.buffer.place_cursor(self.props.buffer.get_iter_at_mark(self.mark))

    def find_first(self, searched_entry):
        self.reset_search()
        self.find_next(searched_entry)

    def find_next(self, searched_entry):
        buffer_iter = self.props.buffer.get_iter_at_mark(self.mark)
        next_occurence = buffer_iter.forward_search(
            searched_entry.get_text(), Gtk.TextSearchFlags.CASE_INSENSITIVE, None
        )

        # Found nothing try from the beginning
        if next_occurence is None:
            next_occurence = self.props.buffer.get_start_iter(
            ).forward_search(searched_entry.get_text(), Gtk.TextSearchFlags.CASE_INSENSITIVE, None)

        # Highlight if result
        if next_occurence is not None:
            self.highlight(next_occurence[0], next_occurence[1])
            self.props.buffer.delete_mark(self.mark)
            self.mark = self.create_new_mark(next_occurence[1])

    def find_previous(self, searched_entry):
        # First go to the beginning of searched_entry string
        buffer_iter = self.props.buffer.get_iter_at_mark(self.mark)
        buffer_iter.backward_chars(len(searched_entry.get_text()))

        previous_occurence = buffer_iter.backward_search(
            searched_entry.get_text(), Gtk.TextSearchFlags.CASE_INSENSITIVE, None
        )

        # Found nothing ? Try from the end
        if previous_occurence is None:
            previous_occurence = self.props.buffer.get_end_iter(
            ).backward_search(searched_entry.get_text(), Gtk.TextSearchFlags.CASE_INSENSITIVE, None)

        # Highlight if result
        if previous_occurence is not None:
            self.highlight(previous_occurence[0], previous_occurence[1])
            self.props.buffer.delete_mark(self.mark)
            self.mark = self.create_new_mark(previous_occurence[1])

    def highlight(self, range_start, range_end):
        self.props.buffer.select_range(range_start, range_end)
        # Focus
        self.scroll_mark_onscreen(self.mark)
