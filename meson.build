project(
  'lutris',
  license: 'GPL-3.0-or-later'
)

# Checking for Python
python_modules = [
  'evdev',
  'gi',
  'requests',
  'yaml',
]
if meson.version().version_compare('>=0.51')
  py = import('python').find_installation(modules: python_modules)
else
  py = import('python').find_installation()
  foreach module: python_modules
    if run_command(py, '-c', 'import @0@'.format(module)).returncode() != 0
      error('Failed to find required python module "@0@".'.format(module))
    endif
  endforeach
endif

# Set folders
bindir = get_option('bindir')
pylibdir = py.get_install_dir()
datadir = get_option('datadir')
localedir = get_option('localedir')

# Translations (see github issue #728)
subdir('po')

# Do installation
install_subdir(
  'bin',
  install_dir: bindir,
  strip_directory: true,
  install_mode: 'rwxr-xr-x',
)
install_subdir(
  'lutris',
  install_dir: pylibdir,
)
install_subdir(
  'share',
  install_dir: datadir,
  strip_directory: true,
)
