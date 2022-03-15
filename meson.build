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
podir = join_paths(meson.source_root(), 'po')

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

desktop_file = i18n.merge_file(
  input: files('share/applications/net.lutris.Lutris.desktop'),
  output: 'net.lutris.Lutris.desktop',
  type: 'desktop',
  po_dir: podir,
  install: true,
  install_dir: join_paths(datadir, 'applications'),
)

# Validate the desktop file
desktop_file_validate = find_program('desktop-file-validate', required:false)
if desktop_file_validate.found()
  test (
    'Validate desktop file',
    desktop_file_validate,
    args: [ desktop_file.full_path() ],
  )
endif

metainfo_file = i18n.merge_file(
  input: files('share/metainfo/net.lutris.Lutris.metainfo.xml'),
  output: 'net.lutris.Lutris.metainfo.xml',
  type: 'xml',
  po_dir: podir,
  install: true,
  install_dir: join_paths(datadir, 'metainfo'),
)

# Validate the metainfo file
appstreamcli = find_program('appstream-util', required: false)
if appstreamcli.found()
  test (
    'Validate metainfo file',
    appstreamcli,
    args: ['validate-relax', '--nonet', metainfo_file.full_path() ]
  )
endif
