"""GtkTemplate compatibility layer for GTK 4.

In GTK 4 with modern PyGObject, Gtk.Template is natively supported.
This module provides the GtkTemplate API that the codebase uses,
implemented on top of the native Gtk.Template support.
"""

import os

from gi.repository import Gio, GLib, Gtk

__all__ = ["GtkTemplate"]


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

        # In GTK 4, signal connections from UI files need BuilderCScope which
        # doesn't work well with Python callbacks. Signals should be connected
        # in Python code (in __init__) instead of in the UI file.

        cls.__gtemplate_methods__ = bound_methods
        cls.__gtemplate_widgets__ = bound_widgets

        base_init_template = cls.init_template

        def patched_init_template(self):
            base_init_template(self)
            for wname in self.__gtemplate_widgets__:
                widget = self.get_template_child(cls, wname)
                self.__dict__[wname] = widget
                if widget is None:
                    raise AttributeError(
                        "Missing child widget '%s'; template may be broken "
                        "(widgets: %s)" % (wname, ", ".join(self.__gtemplate_widgets__))
                    )

        cls.init_template = patched_init_template
        return cls


GtkTemplate = _GtkTemplate
