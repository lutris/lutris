"""GtkTemplate implementation for PyGI

Blog post
http://www.virtualroadside.com/blog/index.php/2015/05/24/gtk3-composite-widget-templates-for-python/

Github
https://github.com/virtuald/pygi-composite-templates/blob/master/gi_composites.py

This should have landed in PyGObect and will be available without this shim in the future.
See: https://gitlab.gnome.org/GNOME/pygobject/merge_requests/52
"""
#
# Copyright (C) 2015 Dustin Spicuzza <dustin@virtualroadside.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301
# USA

from os.path import abspath, join

import inspect
import warnings

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from lutris.gui.dialogs import ErrorDialog

__all__ = ["GtkTemplate"]


class GtkTemplateWarning(UserWarning):
    pass


def _connect_func(builder, obj, signal_name, handler_name, connect_object, flags, cls):
    """Handles GtkBuilder signal connect events"""

    if connect_object is None:
        extra = ()
    else:
        extra = (connect_object,)

    # The handler name refers to an attribute on the template instance,
    # so ask GtkBuilder for the template instance
    template_inst = builder.get_object(cls.__gtype_name__)

    if template_inst is None:  # This should never happen
        errmsg = (
            "Internal error: cannot find template instance! obj: %s; "
            "signal: %s; handler: %s; connect_obj: %s; class: %s"
            % (obj, signal_name, handler_name, connect_object, cls)
        )
        warnings.warn(errmsg, GtkTemplateWarning)
        return

    handler = getattr(template_inst, handler_name)

    if flags == GObject.ConnectFlags.AFTER:
        obj.connect_after(signal_name, handler, *extra)
    else:
        obj.connect(signal_name, handler, *extra)

    template_inst.__connected_template_signals__.add(handler_name)


def _register_template(cls, template_bytes):
    """Registers the template for the widget and hooks init_template"""

    # This implementation won't work if there are nested templates, but
    # we can't do that anyways due to PyGObject limitations so it's ok

    if not hasattr(cls, "set_template"):
        ErrorDialog(
            "Your Linux distribution is too old, Lutris won't function properly"
        )
        raise TypeError("Requires PyGObject 3.13.2 or greater")

    cls.set_template(template_bytes)

    bound_methods = set()
    bound_widgets = set()

    # Walk the class, find marked callbacks and child attributes
    for name in dir(cls):

        o = getattr(cls, name, None)

        if inspect.ismethod(o):
            if hasattr(o, "_gtk_callback"):
                bound_methods.add(name)
                # Don't need to call this, as connect_func always gets called
                # cls.bind_template_callback_full(name, o)
        elif isinstance(o, _Child):
            cls.bind_template_child_full(name, True, 0)
            bound_widgets.add(name)

    # Have to setup a special connect function to connect at template init
    # because the methods are not bound yet
    cls.set_connect_func(_connect_func, cls)

    cls.__gtemplate_methods__ = bound_methods
    cls.__gtemplate_widgets__ = bound_widgets

    base_init_template = cls.init_template
    cls.init_template = lambda s: _init_template(s, cls, base_init_template)


def _init_template(self, cls, base_init_template):
    """This would be better as an override for Gtk.Widget"""

    # TODO: could disallow using a metaclass.. but this is good enough
    # .. if you disagree, feel free to fix it and issue a PR :)
    if self.__class__ is not cls:
        raise TypeError(
            "Inheritance from classes with @GtkTemplate decorators "
            "is not allowed at this time"
        )

    connected_signals = set()
    self.__connected_template_signals__ = connected_signals

    base_init_template(self)

    for name in self.__gtemplate_widgets__:
        widget = self.get_template_child(cls, name)
        self.__dict__[name] = widget

        if widget is None:
            # Bug: if you bind a template child, and one of them was
            #      not present, then the whole template is broken (and
            #      it's not currently possible for us to know which
            #      one is broken either -- but the stderr should show
            #      something useful with a Gtk-CRITICAL message)
            raise AttributeError(
                "A missing child widget was set using "
                "GtkTemplate.Child and the entire "
                "template is now broken (widgets: %s)"
                % ", ".join(self.__gtemplate_widgets__)
            )

    for name in self.__gtemplate_methods__.difference(connected_signals):
        errmsg = (
            "Signal '%s' was declared with @GtkTemplate.Callback "
            + "but was not present in template"
        ) % name
        warnings.warn(errmsg, GtkTemplateWarning)


# TODO: Make it easier for IDE to introspect this
class _Child:
    """
        Assign this to an attribute in your class definition and it will
        be replaced with a widget defined in the UI file when init_template
        is called
    """

    __slots__ = []

    @staticmethod
    def widgets(count):
        """
            Allows declaring multiple widgets with less typing::

                button    \
                label1    \
                label2    = GtkTemplate.Child.widgets(3)
        """
        return [_Child() for _ in range(count)]


class _GtkTemplate:
    """
        Use this class decorator to signify that a class is a composite
        widget which will receive widgets and connect to signals as
        defined in a UI template. You must call init_template to
        cause the widgets/signals to be initialized from the template::

            @GtkTemplate(ui='foo.ui')
            class Foo(Gtk.Box):

                def __init__(self):
                    super().__init__()
                    self.init_template()

        The 'ui' parameter can either be a file path or a GResource resource
        path::

            @GtkTemplate(ui='/org/example/foo.ui')
            class Foo(Gtk.Box):
                pass

        To connect a signal to a method on your instance, do::

            @GtkTemplate.Callback
            def on_thing_happened(self, widget):
                pass

        To create a child attribute that is retrieved from your template,
        add this to your class definition::

            @GtkTemplate(ui='foo.ui')
            class Foo(Gtk.Box):

                widget = GtkTemplate.Child()


        Note: This is implemented as a class decorator, but if it were
        included with PyGI I suspect it might be better to do this
        in the GObject metaclass (or similar) so that init_template
        can be called automatically instead of forcing the user to do it.

        .. note:: Due to limitations in PyGObject, you may not inherit from
                  python objects that use the GtkTemplate decorator.
    """

    __ui_path__ = None

    @staticmethod
    def Callback(f):
        """
            Decorator that designates a method to be attached to a signal from
            the template
        """
        f._gtk_callback = True
        return f

    Child = _Child

    @staticmethod
    def set_ui_path(*path):
        """
            If using file paths instead of resources, call this *before*
            loading anything that uses GtkTemplate, or it will fail to load
            your template file

            :param path: one or more path elements, will be joined together
                         to create the final path

            TODO: Alternatively, could wait until first class instantiation
                  before registering templates? Would need a metaclass...
        """
        _GtkTemplate.__ui_path__ = abspath(join(*path))

    def __init__(self, ui):
        self.ui = ui

    def __call__(self, cls):

        if not issubclass(cls, Gtk.Widget):
            raise TypeError("Can only use @GtkTemplate on Widgets")

        # Nested templates don't work
        if hasattr(cls, "__gtemplate_methods__"):
            raise TypeError("Cannot nest template classes")

        # Load the template either from a resource path or a file
        # - Prefer the resource path first

        try:
            template_bytes = Gio.resources_lookup_data(
                self.ui, Gio.ResourceLookupFlags.NONE
            )
        except GLib.GError:
            ui = self.ui
            if isinstance(ui, (list, tuple)):
                ui = join(ui)

            if _GtkTemplate.__ui_path__ is not None:
                ui = join(_GtkTemplate.__ui_path__, ui)

            with open(ui, "rb") as fp:
                template_bytes = GLib.Bytes.new(fp.read())

        _register_template(cls, template_bytes)
        return cls


# Future shim support if this makes it into PyGI?
# if hasattr(Gtk, 'GtkTemplate'):
#    GtkTemplate = lambda c: c
# else:
GtkTemplate = _GtkTemplate
