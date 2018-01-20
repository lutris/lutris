"""Options list for system config."""
import os
from collections import OrderedDict

from lutris import runners
from lutris.util import display, system

DISPLAYS = None


def get_displays():
    global DISPLAYS
    if not DISPLAYS:
        DISPLAYS = display.get_output_names()
    return DISPLAYS


def get_resolution_choices():
    resolutions = display.get_resolutions()
    resolution_choices = list(zip(resolutions, resolutions))
    resolution_choices.insert(0, ("Keep current", 'off'))
    return resolution_choices


def get_output_choices():
    displays = get_displays()
    output_choices = list(zip(displays, displays))
    output_choices.insert(0, ("Off", 'off'))
    return output_choices


def get_output_list():
    choices = [
        ('Off', 'off'),
    ]
    displays = get_displays()
    for index, output in enumerate(displays):
        # Display name can't be used because they might not be in the right order
        # Using DISPLAYS to get the number of connected monitors
        choices.append(("Monitor {}".format(index + 1), str(index)))
    return choices


def get_dri_prime():
    return len(display.get_providers()) > 1


system_options = [
    {
        'option': 'game_path',
        'type': 'directory_chooser',
        'label': _('Main game folder'),
        'default': os.path.expanduser('~/Games'),
        'scope': ['runner', 'system'],
        'help': ("The main folder where you install your games.\n"
                 "Lutris uses it to propose you a default path when you \n"
                 "install a new game.")
    },
    {
        'option': 'reset_desktop',
        'type': 'bool',
        'label': _('Restore to default resolution when game quits'),
        'default': False,
        'help': ("Some games don't restore your screen resolution when \n"
                 "closed or when they crash. This is when this option comes \n"
                 "into play to save your bacon.")
    },
    {
        'option': 'restore_gamma',
        'type': 'bool',
        'default': False,
        'label': _('Restore default gamma correction after game quits'),
        'help': ("Some games don't correctly restores gamma on exit, making "
                 "your display too bright. Select this option to correct it.")
    },
    {
        'option': 'primusrun',
        'type': 'bool',
        'default': False,
        'condition': system.find_executable('primusrun'),
        'label': _('Use primusrun (NVIDIA Optimus laptops)'),
        'help': ("If you have installed the primus package, selecting this "
                 "option will run the game with the primusrun command, "
                 "activating your NVIDIA graphic chip for high 3D "
                 "performance.")
    },
    {
        'option': 'dri_prime',
        'type': 'bool',
        'default': False,
        'condition': get_dri_prime,
        'label': _('Use PRIME (hybrid graphics on laptops)'),
        'help': ("If you have open source graphic drivers (Mesa), selecting this "
                 "option will run the game with the 'DRI_PRIME=1' environment variable, "
                 "activating your discrete graphic chip for high 3D "
                 "performance.")
    },
    {
        'option': 'sdl_video_fullscreen',
        'type': 'choice',
        'label': _('Fullscreen SDL games to display'),
        'choices': get_output_list,
        'default': 'off',
        'help': ("Hint SDL games to use a specific monitor when going fullscreen by "
                 "setting the SDL_VIDEO_FULLSCREEN environment variable")
    },
    {
        'option': 'display',
        'type': 'choice',
        'label': _('Turn off monitors except'),
        'choices': get_output_choices,
        'default': 'off',
        'help': ("Only keep the selected screen active while the game is "
                 "running. \n"
                 "This is useful if you have a dual-screen setup, and are \n"
                 "having display issues when running a game in fullscreen.")
    },
    {
        'option': 'resolution',
        'type': 'choice',
        'label': _('Switch resolution to'),
        'choices': get_resolution_choices,
        'default': 'off',
        'help': "Switch to this screen resolution while the game is running."
    },
    {
        'option': 'terminal',
        'label': _("Run in a terminal"),
        'type': 'bool',
        'default': False,
        'advanced': True,
        'help': "Run the game in a new terminal window."
    },
    {
        'option': 'terminal_app',
        'label': _("Terminal application"),
        'type': 'choice_with_entry',
        'choices': system.get_terminal_apps,
        'default': system.get_default_terminal(),
        'advanced': True,
        'help': ("The terminal emulator to be run with the previous option."
                 "Choose from the list of detected terminal apps or enter "
                 "the terminal's command or path."
                 "Note: Not all terminal emulators are guaranteed to work.")
    },
    {
        'option': 'env',
        'type': 'mapping',
        'label': _('Environment variables'),
        'advanced': True,
        'help': _("Environment variables loaded at run time")
    },
    {
        'option': 'prefix_command',
        'type': 'string',
        'label': _('Command prefix'),
        'advanced': True,
        'help': ("Command line instructions to add in front of the game's "
                 "execution command.")
    },
    {
        'option': 'include_processes',
        'type': 'string',
        'label': _('Include processes'),
        'advanced': True,
        'help': ('What processes to include in process monitoring. '
                 'This is to override the built-in exclude list.\n'
                 'Space-separated list, processes including spaces '
                 'can be wrapped in quotation marks.')
    },
    {
        'option': 'exclude_processes',
        'type': 'string',
        'label': _('Exclude processes'),
        'advanced': True,
        'help': ('What processes to exclude in process monitoring. '
                 'For example background processes that stick around '
                 'after the game has been closed.\n'
                 'Space-separated list, processes including spaces '
                 'can be wrapped in quotation marks.')
    },
    {
        'option': 'single_cpu',
        'type': 'bool',
        'label': _('Restrict to single core'),
        'advanced': True,
        'default': False,
        'help': "Restrict the game to a single CPU core."
    },
    {
        'option': 'disable_runtime',
        'type': 'bool',
        'label': _('Disable Lutris Runtime'),
        'default': False,
        'advanced': True,
        'help': ("The Lutris Runtime loads some libraries before running the "
                 "game. Which can cause some incompatibilities in some cases. "
                 "Check this option to disable it.")
    },
    {
        'option': 'disable_monitoring',
        'label': _("Disable process monitor"),
        'type': 'bool',
        'default': False,
        'advanced': True,
        'help': "Disables process monitoring of games, Lutris won't detect when game quits."
    },
    {
        'option': 'reset_pulse',
        'type': 'bool',
        'label': _('Reset PulseAudio'),
        'default': False,
        'advanced': True,
        'condition': system.find_executable('pulseaudio'),
        'help': "Restart PulseAudio before launching the game."
    },
    {
        'option': 'pulse_latency',
        'type': 'bool',
        'label': _('Reduce PulseAudio latency'),
        'default': False,
        'advanced': True,
        'condition': system.find_executable('pulseaudio'),
        'help': ('Set the environment variable PULSE_LATENCY_MSEC=60 to improve '
                 'audio quality on some games')
    },
    {
        'option': 'use_us_layout',
        'type': 'bool',
        'label': _('Switch to US keyboard layout'),
        'default': False,
        'advanced': True,
        'help': 'Switch to US keyboard qwerty layout while game is running'
    },
    {
        'option': 'killswitch',
        'type': 'string',
        'label': _('Killswitch file'),
        'advanced': True,
        'help': ("Path to a file which will stop the game when deleted \n"
                 "(usually /dev/input/js0 to stop the game on joystick "
                 "unplugging)")
    },
    {
        'option': 'xboxdrv',
        'type': 'string',
        'label': _('xboxdrv config'),
        'advanced': True,
        'condition': system.find_executable('xboxdrv'),
        'help': ("Command line options for xboxdrv, a driver for XBOX 360 "
                 "controllers. Requires the xboxdrv package installed.")
    },
    {
        'option': 'sdl_gamecontrollerconfig',
        'type': 'string',
        'label': _('SDL2 gamepad mapping'),
        'advanced': True,
        'help': ("SDL_GAMECONTROLLERCONFIG mapping string or path to a custom "
                 "gamecontrollerdb.txt file containing mappings.")
    },
    {
        'option': 'xephyr',
        'type': 'choice',
        'label': _("Use Xephyr"),
        'type': 'choice',
        'choices': (
            ('Off', 'off'),
            ('8BPP (256 colors)', '8bpp'),
            ('16BPP (65536 colors)', '16bpp')
        ),
        'default': 'off',
        'advanced': True,
        'help': "Run program in Xephyr to support 8BPP and 16BPP color modes",
    },
    {
        'option': 'xephyr_resolution',
        'type': 'string',
        'label': _('Xephyr resolution'),
        'advanced': True,
        'help': 'Screen resolution of the Xephyr server'
    },
]


def with_runner_overrides(runner_slug):
    """Return system options updated with overrides from given runner."""
    options = system_options
    try:
        runner = runners.import_runner(runner_slug)
    except runners.InvalidRunner:
        return options
    if not getattr(runner, 'system_options_override'):
        runner = runner()
    if runner.system_options_override:
        opts_dict = OrderedDict((opt['option'], opt) for opt in options)
        for option in runner.system_options_override:
            key = option['option']
            if opts_dict.get(key):
                opts_dict[key] = opts_dict[key].copy()
                opts_dict[key].update(option)
            else:
                opts_dict[key] = option
        options = [opt for opt in list(opts_dict.values())]
    return options
