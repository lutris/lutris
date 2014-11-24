from lutris.util import display


oss_list = [
    ("None (don't use OSS)", "none"),
    ("padsp (PulseAudio OSS Wrapper)", "padsp"),
    ("padsp32 (PulseAudio OSS Wrapper for 32bit apps)", "padsp32"),
    ("pasuspender", "pasuspender"),
    ("aoss (OSS Wrapper for Alsa)", "aoss"),
]

resolutions = display.get_resolutions()
resolution_choices = zip(resolutions, resolutions)
resolution_choices.insert(0, ("No change", None))

outputs = display.get_output_names()
output_choices = zip(outputs, outputs)
output_choices.insert(0, ("No change", None))
system_options = [
    {
        'option': 'game_path',
        'type': 'directory_chooser',
        'label': 'Library default folder',
        'help': ("The main folder where you install your games.\n"
                 "Lutris uses it to propose you a default path when you \n"
                 "install a new game.")
    },
    {
        'option': 'resolution',
        'type': 'choice',
        'label': 'Screen resolution',
        'choices': resolution_choices,
        'help': "Switch to this screen resolution while the game is running."
    },
    {
        'option': 'reset_desktop',
        'type': 'bool',
        'label': 'Restore desktop resolution when the game quits',
        'default': True,
        'help': ("Some games don't restore your screen resolution when \n"
                 "closed or when they crash. This is when this option comes \n"
                 "into play to save your bacon.")
    },
    {
        'option': 'restore_gamma',
        'type': 'bool',
        'default': False,
        'label': 'Restore default gamma correction after game quits',
        'help': ("Some games don't correctly restores gamma on exit, making "
                 "your display too bright. Select this option to correct it.")
    },
    {
        'option': 'primusrun',
        'type': 'bool',
        'default': False,
        'label': 'Use primusrun (NVIDIA Optimus laptops)',
        'help': ("If you have installed the primus package, selecting this "
                 "option will run the game with the primusrun command, "
                 "activating your NVIDIA graphic chip for high 3D "
                 "performance.")
    },
    {
        'option': 'display',
        'type': 'choice',
        'label': 'Restrict to display',
        'choices': output_choices,
        'help': ("Only keep the selected screen active while the game is "
                 "running. \n"
                 "This is used if you have a dual-screen setup, and are \n"
                 "having display issues when running a game in fullscreen.")
    },
    {
        'option': 'prefix_command',
        'type': 'string',
        'label': 'Prefix command',
        'help': ("Name of a program that will launch the game, making "
                 "alterations to its behavior. \n"
                 "Examples: padsp, glxosd, optirun")
    },
    {
        'option': 'reset_pulse',
        'type': 'bool',
        'label': 'Reset PulseAudio',
        'help': "Restart PulseAudio before launching the game."
    },
    {
        'option': 'killswitch',
        'type': 'string',
        'label': 'Killswitch file',
        'help': ("Path to a file which will stop the game when deleted \n"
                 "(usually /dev/input/js0 to stop the game on joystick "
                 "unplugging)")
    },
    {
        'option': 'xboxdrv',
        'type': 'string',
        'label': 'xboxdrv config',
        'help': ("Command line options for xboxdrv, a driver for XBOX 360"
                 "controllers")
    }
]
