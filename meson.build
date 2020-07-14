project(
  'lutris',
  license: 'GPL-3.0-or-later'
)

# Find Python installation
python = import('python').find_installation()

# Set folders
prefix = get_option('prefix')
bindir = get_option('bindir')
pylibdir = python.get_install_dir()
datadir = get_option('datadir')
localedir = get_option('localedir')
mandir = get_option('mandir')
lutrisdir = join_paths(pylibdir, 'lutris')

# Generate configuration files
config = configuration_data()
config.set('localedir_path', join_paths(prefix, localedir))

configure_file(
  input: 'optional_settings.py.in',
  output: 'optional_settings.py',
  configuration: config,
  install: true,
  install_dir: lutrisdir,
)

# Translations
subdir('po')

# Do installation
install_data(
  files('bin/lutris'),
  install_dir: bindir,
  install_mode: 'rwxr-xr-x',
)

install_subdir(
  'lutris',
  install_dir: pylibdir,
)

install_subdir(
  'share/applications',
  install_dir: join_paths(datadir, 'applications'),
  strip_directory: true,
)

install_subdir(
  'share/icons',
  install_dir: join_paths(datadir, 'icons'),
  strip_directory: true,
)

install_subdir(
  'share/lutris',
  install_dir: join_paths(datadir, 'lutris'),
  strip_directory: true,
)

install_man(
  files('share/man/man1/lutris.1'),
  install_dir: join_paths(mandir, 'man1'),
)

install_subdir(
  'share/metainfo',
  install_dir: join_paths(datadir, 'metainfo'),
  strip_directory: true,
)
