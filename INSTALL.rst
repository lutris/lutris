Installing Lutris
=================

Requirements
------------

Lutris should work on any Gnome system, the following depencies should be
installed:

    * python > 3.4
    * python-yaml
    * PyGobject
    * libsoup-gnome

Installation
------------

Lutris uses Python's distutils framework for installation. In order to
install Lutris, you will need root access. To install Lutris, perform
the following command as root::

      $ python3 setup.py install

**Warning:** USING SETUP.PY TO INSTALL LUTRIS IS ENTIRELY UNSUPPORTED BY
THE DEVELOPERS. USE THAT METHOD AT YOUR OWN RISK. THE RECOMMENDED WAY OF
INSTALLING LUTRIS IS WITH PROVIDED DISTRIBUTION PACKAGES. IF YOU WANT TO 
USE THE DEVELOPMENT VERSION, JUST RUN IT FROM THE SOURCE DIR ITSELF.

***********************************************************
*                                                         *
* **WARNING:** SERIOUSLY, DO ***NOT*** USE SETUP.PY!!!!!  *
*                                                         *
***********************************************************

**Warning:** there is no way to cleanly uninstall programs installed with
setup.py other than manuall deleting the created files. Prefer installing
Lutris through distribution packages or run it directly from the source
directory::

    cd /path/to/lutris/source
    ./bin/lutris

Run Lutris
-----------

If you installed Lutris using the setup.py script, you can launch the
program by typing "lutris" at the command line. If you want to run
Lutris without installing it, start "bin/lutris" from within the
Lutris directory.
