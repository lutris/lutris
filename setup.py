#!/usr/bin/python2
# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 3 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import sys

from distutils.core import setup

from lutris.settings import VERSION


def update_data_path(prefix, oldvalue=None):
    try:
        fin = file('lutris/lutrisconfig.py', 'r')
        fout = file(fin.name + '.new', 'w')

        for line in fin:
            fields = line.split(' = ')  # Separate variable from value
            if fields[0] == '__lutris_data_directory__':
                # update to prefix, store oldvalue
                if not oldvalue:
                    oldvalue = fields[1]
                    line = "%s = '%s'\n" % (fields[0], prefix)
                else:  # restore oldvalue
                    line = "%s = %s" % (fields[0], oldvalue)
            fout.write(line)

        fout.flush()
        fout.close()
        fin.close()
        os.rename(fout.name, fin.name)
    except (OSError, IOError):
        print ("ERROR: Can't find lutris/lutrisconfig.py")
        sys.exit(1)
    return oldvalue


data_files = []

for directory, _, filenames in os.walk(u'share'):
    dest = directory[6:]
    if filenames:
        files = []
        for filename in filenames:
            filename = os.path.join(directory, filename)
            files.append(filename)
        data_files.append((os.path.join('share', dest), files))


setup(
    name='lutris',
    version=VERSION,
    license='GPL-3',
    author='Mathieu Comandon',
    author_email='strider@strycore.com',
    packages=['lutris', 'lutris.gui', 'lutris.util', 'lutris.runners',
              'lutris.installer', 'lutris.migrations'],
    scripts=['bin/lutris'],
    data_files=data_files,
    # FIXME: find a way to install dependencies
    #install_requires=['PyYAML', 'PyGObject', 'dbus-python', 'pyxdg'],
    url='https://lutris.net',
    description='Install and play any video game on Linux',
    long_description="""Lutris is a gaming platform for GNU/Linux. It's goal is
    to make gaming on Linux as easy as possible by taking care of installing
    and setting up the game for the user. The only thing you have to do is play
    the game. It aims to support every game that is playable on Linux.""",
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GPLv3',
        'Programming Language :: Python',
        'Operating System :: Linux',
        'Topic :: Games'
    ],
)
