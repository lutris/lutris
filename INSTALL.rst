Installing Lutris
=================

Requirements
------------

Lutris should work on any Gnome system, the following depencies should be
installed:

    * meson >= 0.40.0 (build-only)
    * python > 3.4
    * python-yaml
    * PyGobject
    * libsoup-gnome

Installation
------------

Lutris uses Python's distutils framework for installation. In order to
install Lutris, you will need root access. To install Lutris, perform
the following commands::

      $ meson _build
      # ninja -C _build install
