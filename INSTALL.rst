Installing Lutris
=================

Requirements
------------

Lutris should work on any Gnome system, the following depencies should be
installed:

    * python == 2.7
    * python-xdg
    * python-yaml
    * PyGobject
    * libsoup-gnome

Installation
------------

Lutris uses Python's distutils framework for installation. In order to
install Lutris, you will need root access. To install Lutris, perform
the following command as root:

      $ python setup.py install

Run Lutris
-----------

If you installed Lutris using the setup.py script, you can launch the
program by typing "lutris" at the command line. If you want to run
Lutris without installing it, start "bin/lutris" from within the
Lutris directory.

Packaging
---------

On Fedora:
These instructions should let you build a Lutris on a minimal Fedora
system such as a LXC container.

Install required packaging tools::

    yum install @development-tools
    yum install fedora-packager

Create a user to build the package with::

    useradd makerpm
    usermod -a -G mock makerpm
    passwd makerpm

Log out of the root account and login as the makerpm user then create the
required directory structure::

    rpmdev-setuptree
