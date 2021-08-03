#!/usr/bin/env python3
import os
import sys

from setuptools import setup

from lutris import __version__ as VERSION

if sys.version_info < (3, 4):
    sys.exit('Python 3.4 is required to run Lutris')

data_files = []

for directory, _, filenames in os.walk(u'share'):
    dest = directory[6:]
    if filenames:
        files = [os.path.join(directory, filename) for filename in filenames]
        data_files.append((os.path.join('share', dest), files))

setup(
    name='lutris',
    version=VERSION,
    license='GPL-3',
    author='Mathieu Comandon',
    author_email='strider@strycore.com',
    packages=[
        'lutris',
        'lutris.database',
        'lutris.gui',
        'lutris.gui.config',
        'lutris.gui.dialogs',
        'lutris.gui.installer',
        'lutris.gui.views',
        'lutris.gui.widgets',
        'lutris.installer',
        'lutris.migrations',
        'lutris.runners',
        'lutris.runners.commands',
        'lutris.scanners',
        'lutris.services',
        'lutris.util',
        'lutris.util.dolphin',
        'lutris.util.egs',
        'lutris.util.graphics',
        'lutris.util.mame',
        'lutris.util.steam',
        'lutris.util.retroarch',
        'lutris.util.wine'
    ],
    scripts=['bin/lutris'],
    data_files=data_files,
    zip_safe=False,
    install_requires=[
        'PyYAML',
        'PyGObject',
        'evdev',
        'requests',
        'python-magic'
    ],
    url='https://lutris.net',
    description='Video game preservation platform',
    long_description="""Lutris helps you install and play video games from all eras
    and from most gaming systems. By leveraging and combining existing emulators,
    engine re-implementations and compatibility layers, it gives you a central
    interface to launch all your games.""",
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python',
        'Operating System :: Linux',
        'Topic :: Games/Entertainment'
    ],
)
