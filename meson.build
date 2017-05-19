project('lutris',
  meson_version: '>= 0.40.0',
  version: '0.4.10',
  license: 'GPL-3'
)

python = import('python3')
python3_path = python.find_python().path()
purelibdir = python.sysconfig_path('purelib')
install_subdir('lutris', install_dir: purelibdir)

subdir('bin')
subdir('share')
subdir('po')

nose = find_program(['nosetests-3', 'nosetests'])
if nose.found()
  test('tests', nose, args: [meson.source_root()])
endif

meson.add_install_script('meson_post_install.py')
