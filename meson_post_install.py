#!/usr/bin/env python3

import os
import pathlib
import sysconfig
import compileall
import subprocess

prefix = pathlib.Path(os.environ.get('MESON_INSTALL_PREFIX', '/usr/local'))
datadir = prefix / 'share'
destdir = os.environ.get('DESTDIR', '')

if not destdir:
    print('Updating icon cache...')
    subprocess.call(['gtk-update-icon-cache', '-qtf', str(datadir / 'icons' / 'hicolor')])

    print('Updating desktop database...')
    subprocess.call(['update-desktop-database', '-q', str(datadir / 'applications')])

print('Compiling python bytecode...')
moduledir = sysconfig.get_path('purelib', vars={'base': str(prefix)})
compileall.compile_dir(destdir + os.path.join(moduledir, 'lutris'), optimize=2)
