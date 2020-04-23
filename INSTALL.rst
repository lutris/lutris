Installing Lutris
=================

Requirements
------------

Lutris should work on any up to date Linux system. It is based on Python and
Gtk but will run on any desktop environment.
If you installed Lutris from our PPA or some other repository, it should already
come with all of its essential dependencies. However, if you need to install
Lutris manually, it requires the following components:

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
  * The 32bit OpenGL and Vulkan drivers for your graphics card
  * Wine (not actually needed, but installing it is the easiest way to get all
    the libraries missing from our runtime).

To install all those dependencies (except for Wine and graphics drivers)
on Ubuntu based systems, you can run::

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

To install Lutris, please follow instructions listed on our `Downloads Page <https://lutris.net/downloads/>`_.
Getting Lutris from a PPA or a repository is the preferred way of installing
it and we *strongly advice* to use this method if you can.

However, if the instructions on our Downloads page don't apply to your Linux
distribution or there's some other reason you can't get it from a package,
you can run it directly from the source directory::

    git clone https://github.com/lutris/lutris
    cd lutris
    ./bin/lutris
    
Alternatively you can install Lutris manually with the help of **virtualenv**.

First, install ``python-virtualenv`` from your distribution's 
repositories, along with dependencies listed in Requirements_.
Then, create and activate virtual environment for Lutris::

    virtualenv --system-site-packages ~/lutris
    source ~/lutris/bin/activate

While in the virtual environment, run the installation script::

    python3 setup.py install

Run Lutris
-----------

If you installed Lutris using a package, you can launch the program by typing
``lutris`` at the command line (same applies to virtualenv method, but you need to
activate the virtual environment first). And if you want to run Lutris without
installing it, start ``./bin/lutris`` from within the source directory.
