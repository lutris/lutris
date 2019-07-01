project('lutris')

pymod = import('python')
# Checking for Python
python  = pymod.find_installation('python3', required: true, modules: ['yaml', 'gi', 'evdev', 'requests'])
python_version     = python.language_version()
python_version_min = '>=3.4'
if not python_version.version_compare(python_version_min)
  error('Python @0@ required, found Python @1@.'.format(python_version_min, python_version))
endif

# Do installation
install_subdir('lutris', install_dir: 'lib/lutris')
install_subdir('share',  install_dir: 'share', strip_directory: true)
install_subdir('bin',    install_dir: 'bin'  , strip_directory: true, install_mode: 'rwxr-xr-x')
