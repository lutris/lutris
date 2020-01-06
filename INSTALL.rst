Installing Lutris
=================

Requirements
------------

Lutris should work on any up to date Linux system. It is based on Python and
Gtk but will run on any desktop environment. The following dependencies should
be installed:

    * Python > 3.4
    * PyGObject
    * PyGObject bindings for: Gtk, Gdk, GnomeDesktop, Webkit2, Notify
    * python3-requests
    * python3-pillow
    * python3-yaml
    * python3-setproctitle
    * python3-distro
    * python3-evdev (optional, for controller detection)

These dependencies are only for running the Lutris client. To install and run
games themselves we recommend you install the following packages:

  * psmisc (or the package providing 'fuser')
  * pz7zip (or the package providing '7z')
  * curl
  * fluid-soundfont-gs (or other soundfonts for MIDI support)
  * cabextract (if needed, to install Windows games)
  * x11-xserver-utils (or the package providing 'xrandr', if you are running
    Xorg, if you are not, you will depend on the GnomeDesktop bindings to fetch
    screen resolutions on Wayland, the GnomeDesktop library is not directly
    related to the Gnome desktop and is only used as a xrandr replacement.)
  * libc6-i386 and lib32gcc1 for 32bit games support
  * The 32bit OpenGL driver for your graphics card

To install all those dependencies on Ubuntu based systems, you can run::

    sudo apt install python3-yaml python3-requests python3-pil python3-gi \
      gir1.2-gtk-3.0 gir1.2-gnomedesktop-3.0 gir1.2-webkit2-4.0 \
      gir1.2-notify-0.7 psmisc cabextract unzip p7zip curl fluid-soundfont-gs \
      x11-xserver-utils python3-evdev libc6-i386 lib32gcc1 libgirepository1.0-dev \
      python3-setproctitle python3-distro

Note :
If you use OpenSUSE, some dependencies are missing. You need to install python3-gobject-Gdk and typelib-1_0-Gtk-3_0

``sudo apt install python3-gobject-Gdk typelib-1_0-Gtk-3_0``

Installation
------------

Lutris uses Python's distutils framework for installation. In order to
install Lutris, you will need root access. To install Lutris, perform
the following command::

      sudo python3 setup.py install

Although this is the standard way of installing Python packages we STRONGLY
advice against using it. You won't be able to easily remove the installed
version without you having to go through /usr/local and manually delete lutris
related files. The setup.py script is used by packaging tools to build the
actual packages.

Prefer installing Lutris through distribution packages or run it directly
from the source directory::

    git clone https://github.com/lutris/lutris
    cd lutris
    ./bin/lutris

Run Lutris
-----------

If you installed Lutris using a package or the setup.py script, you can launch
the program by typing "lutris" at the command line. If you want to run Lutris
without installing it, start "bin/lutris" from within the Lutris directory.
