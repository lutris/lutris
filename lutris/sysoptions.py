import os
from lutris.util import display, system


oss_list = [
    ("None (don't use OSS)", "none"),
    ("padsp (PulseAudio OSS Wrapper)", "padsp"),
    ("padsp32 (PulseAudio OSS Wrapper for 32bit apps)", "padsp32"),
    ("pasuspender", "pasuspender"),
    ("aoss (OSS Wrapper for Alsa)", "aoss"),
]

resolutions = display.get_resolutions()
resolution_choices = zip(resolutions, resolutions)
resolution_choices.insert(0, ("Keep current", 'off'))

outputs = display.get_output_names()
output_choices = zip(outputs, outputs)
output_choices.insert(0, ("Off", 'off'))
system_options = [
    {
        'option': 'game_path',
        'type': 'directory_chooser',
        'label': 'Main directory',
        'default': os.path.expanduser('~/Games'),
        'scope': ['runner', 'system'],
        'help': ("The main folder where you install your games.\n"
                 "Lutris uses it to propose you a default path when you \n"
                 "install a new game.")
    },
    {
        'option': 'reset_desktop',
        'type': 'bool',
        'label': 'Restore desktop resolution when game quits',
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
        'condition': system.find_executable('primusrun'),
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
        'default': 'off',
        'help': ("Only keep the selected screen active while the game is "
                 "running. \n"
                 "This is useful if you have a dual-screen setup, and are \n"
                 "having display issues when running a game in fullscreen.")
    },
    {
        'option': 'resolution',
        'type': 'choice',
        'label': 'Switch resolution to',
        'choices': resolution_choices,
        'default': 'off',
        'help': "Switch to this screen resolution while the game is running."
    },
    {
        'option': 'terminal',
        'label': "Run in a terminal",
        'type': 'bool',
        'default': False,
        'advanced': True,
        'help': "Run the game in a new terminal window."
    },
    {
        'option': 'terminal_app',
        'label': "Terminal application",
        'type': 'choice_with_entry',
        'choices': system.get_terminal_apps(),
        'default': system.get_default_terminal(),
        'advanced': True,
        'help': ("The terminal emulator to be run with the previous option."
                 "Choose from the list of detected terminal apps or enter "
                 "the terminal's command or path."
                 "Note: Not all terminal emulators are guaranteed to work.")
    },
    {
        'option': 'prefix_command',
        'type': 'string',
        'label': 'Command prefix',
        'advanced': True,
        'help': ("Command line instructions to add in front of the game's "
                 "execution command.")
    },
    {
        'option': 'disable_runtime',
        'type': 'bool',
        'label': 'Disable Lutris Runtime',
        'default': False,
        'advanced': True,
        'help': ("The Lutris Runtime loads some libraries before running the "
                 "game. Which can cause some conflicts in some cases (mostly "
                 "with Steam). Check this option to diasble it.")
    },
    {
        'option': 'reset_pulse',
        'type': 'bool',
        'label': 'Reset PulseAudio',
        'default': False,
        'advanced': True,
        'condition': system.find_executable('pulseaudio'),
        'help': "Restart PulseAudio before launching the game."
    },
    {
        'option': 'killswitch',
        'type': 'string',
        'label': 'Killswitch file',
        'advanced': True,
        'help': ("Path to a file which will stop the game when deleted \n"
                 "(usually /dev/input/js0 to stop the game on joystick "
                 "unplugging)")
    },
    {
        'option': 'xboxdrv',
        'type': 'string',
        'label': 'xboxdrv config',
        'advanced': True,
        'condition': system.find_executable('xboxdrv'),
        'help': ("Command line options for xboxdrv, a driver for XBOX 360"
                 "controllers. Requires the xboxdrv package installed.")
    }
]
