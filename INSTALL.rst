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

      $ python setup.py install

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

Packaging
---------

On Fedora:
These instructions should let you build a Lutris on a minimal Fedora
system such as a LXC container.

Install required packaging tools::

    yum install @development-tools
    yum install fedora-packager
    yum install python-devel
    yum install pyxdg

Create a user to build the package with::

    useradd makerpm
    usermod -a -G mock makerpm
    passwd makerpm

Log out of the root account and login as the makerpm user then create the
required directory structure::

    rpmdev-setuptree

You can now fetch the lutris sources either from a local drive or
remotely::

    cd ~/rpmbuild/SOURCES
    curl -O  https://lutris.net/releases/lutris_0.3.7.tar.gz

Extract the specs file from the archive::

    cd ../SPECS/
    tar xvzf ../SOURCES/lutris_0.3.7.tar.gz lutris/lutris.spec
    mv lutris/lutris.spec .
    rmdir lutris

You can now build the RPM::

    rpmbuild -ba lutris.spec

The resulting package will be available at
~/rpmbuild/RPMS/noarch/lutris-0.3.7-3.fc20.noarch.rpm
