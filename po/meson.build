i18n = import('i18n')

run_target(
  'build',
  command: './autogen.sh'
)

i18n.gettext(
  'lutris',
  install_dir: localedir,
  args: '--from-code=UTF-8'
)
