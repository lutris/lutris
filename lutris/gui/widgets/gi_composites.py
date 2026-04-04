"""GtkTemplate compatibility layer for GTK 4.

In GTK 4 with modern PyGObject, Gtk.Template is natively supported.
This module provides the GtkTemplate API that the codebase uses,
implemented on top of the native Gtk.Template support.
"""

import os
import xml.etree.ElementTree as ET

from gi.repository import Gio, GLib, Gtk

__all__ = ["GtkTemplate"]


def _extract_signals(template_bytes):
    """Parse signal elements from template XML, return (cleaned_bytes, signals_list).
    Each signal entry is (object_id_or_None, signal_name, handler_name).
    Signal elements are removed from the XML so GTK doesn't try to resolve them."""
    xml_text = template_bytes.get_data().decode("utf-8")
    root = ET.fromstring(xml_text)

    signals = []

    def walk(element, parent_id):
        """Walk the XML tree, tracking the nearest ancestor object/template id."""
        current_id = parent_id

        if element.tag in ("object", "template"):
            current_id = element.get("id")
            # For <template> without an id, use None to mean "self"
            if element.tag == "template" and current_id is None:
                current_id = None

        children_to_remove = []
        for child in element:
            if child.tag == "signal":
                handler = child.get("handler")
                signal_name = child.get("name")
                if handler and signal_name:
                    signals.append((current_id, signal_name, handler))
                children_to_remove.append(child)
            else:
                walk(child, current_id)

        for child in children_to_remove:
            element.remove(child)

    walk(root, None)

    cleaned = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return GLib.Bytes.new(cleaned.encode("utf-8")), signals


class _Child:
    """Placeholder for template child widgets. Replaced at init_template time."""

    __slots__ = []

    @staticmethod
    def widgets(count):
        return [_Child() for _ in range(count)]


class _GtkTemplate:
    """Decorator that registers a class as a GTK 4 composite template widget.

    Usage::

        @GtkTemplate(ui='foo.ui')
        class Foo(Gtk.Box):
            widget = GtkTemplate.Child()

            def __init__(self):
                super().__init__()
                self.init_template()

            @GtkTemplate.Callback
            def on_thing_happened(self, widget):
                pass
    """

    __ui_path__ = None

    @staticmethod
    def Callback(f):
        """Decorator that marks a method as a template signal callback."""
        f._gtk_callback = True
        return f

    Child = _Child

    @staticmethod
    def set_ui_path(*path):
        _GtkTemplate.__ui_path__ = os.path.abspath(os.path.join(*path))

    def __init__(self, ui):
        self.ui = ui

    def __call__(self, cls):
        if not issubclass(cls, Gtk.Widget):
            raise TypeError("Can only use @GtkTemplate on Widgets")

        # Load template bytes
        try:
            template_bytes = Gio.resources_lookup_data(self.ui, Gio.ResourceLookupFlags.NONE)
        except GLib.GError:
            ui = self.ui
            if isinstance(ui, (list, tuple)):
                ui = " ".join(ui)
            if _GtkTemplate.__ui_path__ is not None:
                ui = os.path.join(_GtkTemplate.__ui_path__, ui)
            with open(ui, "rb") as fp:
                template_bytes = GLib.Bytes.new(fp.read())

        # Extract <signal> elements and strip them from the template XML
        # so GTK doesn't try to resolve them via BuilderScope
        template_bytes, template_signals = _extract_signals(template_bytes)

        cls.set_template(template_bytes)

        bound_widgets = set()
        bound_methods = set()

        # Find child widgets and callback methods
        for name in dir(cls):
            o = getattr(cls, name, None)
            if isinstance(o, _Child):
                cls.bind_template_child_full(name, True, 0)
                bound_widgets.add(name)
            elif callable(o) and getattr(o, "_gtk_callback", False):
                bound_methods.add(name)

        cls.__gtemplate_methods__ = bound_methods
        cls.__gtemplate_widgets__ = bound_widgets
        cls.__gtemplate_signals__ = template_signals

        base_init_template = cls.init_template

        def patched_init_template(self):
            base_init_template(self)

            # Bind child widgets to instance attributes
            for wname in self.__gtemplate_widgets__:
                widget = self.get_template_child(cls, wname)
                self.__dict__[wname] = widget
                if widget is None:
                    raise AttributeError(
                        "Missing child widget '%s'; template may be broken "
                        "(widgets: %s)" % (wname, ", ".join(self.__gtemplate_widgets__))
                    )

            # Connect signals that were stripped from the template XML
            for obj_id, signal_name, handler_name in self.__gtemplate_signals__:
                handler = getattr(self, handler_name, None)
                if handler is None:
                    continue

                if obj_id is None:
                    # Signal on the template widget itself
                    self.connect(signal_name, handler)
                else:
                    # Signal on a named child widget
                    child = self.get_template_child(cls, obj_id)
                    if child is not None:
                        child.connect(signal_name, handler)

        cls.init_template = patched_init_template
        return cls


GtkTemplate = _GtkTemplate
