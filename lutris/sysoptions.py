"""Options list for system config."""
import os
import glob
from collections import OrderedDict

from lutris import runners
from lutris.util import display, system


def get_optirun_choices():
    """Return menu choices (label, value) for Optimus"""
    choices = [("Off", "off")]
    if system.find_executable("primusrun"):
        choices.append(("primusrun", "primusrun"))
    if system.find_executable("optirun"):
        choices.append(("optirun/virtualgl", "optirun"))
    if system.find_executable("pvkrun"):
        choices.append(("primus vk", "pvkrun"))
    return choices


def get_vk_icd_choices():
    """Return available Vulkan ICD loaders"""
    choices = [("Auto", "")]

    # Add loaders from standard location
    for loader in glob.glob("/usr/share/vulkan/icd.d/*.json"):
        choices.append((os.path.basename(loader), loader))

    # Also add loaders for the AMD GPU Pro driver
    # https://github.com/Tk-Glitch/PKGBUILDS/tree/master/amdgpu-pro-vulkan-only
    for loader in glob.glob("/opt/amdgpu-pro/etc/vulkan/icd.d/*.json"):
        choices.append((os.path.basename(loader), loader))
    return choices


system_options = [  # pylint: disable=invalid-name
    {
        "option": "game_path",
        "type": "directory_chooser",
        "label": "Default installation folder",
        "default": os.path.expanduser("~/Games"),
        "scope": ["runner", "system"],
        "help": "The default folder where you install your games."
    },
    {
        "option": "disable_runtime",
        "type": "bool",
        "label": "Disable Lutris Runtime",
        "default": False,
        "help": (
            "The Lutris Runtime loads some libraries before running the "
            "game. Which can cause some incompatibilities in some cases. "
            "Check this option to disable it."
        ),
    },
    {
        "option": "prefer_system_libs",
        "type": "bool",
        "label": "Prefer system libraries",
        "default": True,
        "help": (
            "When the runtime is enabled, prioritize the system libraries"
            " over the provided ones."
        ),
    },
    {
        "option": "reset_desktop",
        "type": "bool",
        "label": "Restore resolution on game exit",
        "default": False,
        "help": (
            "Some games don't restore your screen resolution when \n"
            "closed or when they crash. This is when this option comes \n"
            "into play to save your bacon."
        ),
    },
    {
        "option": "single_cpu",
        "type": "bool",
        "label": "Restrict to single core",
        "advanced": True,
        "default": False,
        "help": "Restrict the game to a single CPU core.",
    },
    {
        "option": "restore_gamma",
        "type": "bool",
        "default": False,
        "label": "Restore gamma on game exit",
        "advanced": True,
        "help": (
            "Some games don't correctly restores gamma on exit, making "
            "your display too bright. Select this option to correct it."
        ),
    },
    {
        "option": "disable_compositor",
        "label": "Disable desktop effects",
        "type": "bool",
        "default": False,
        "advanced": True,
        "help": (
            "Disable desktop effects while game is running, "
            "reducing stuttering and increasing performance"
        ),
    },
    {
        "option": "reset_pulse",
        "type": "bool",
        "label": "Reset PulseAudio",
        "default": False,
        "advanced": True,
        "condition": system.find_executable("pulseaudio"),
        "help": "Restart PulseAudio before launching the game.",
    },
    {
        "option": "pulse_latency",
        "type": "bool",
        "label": "Reduce PulseAudio latency",
        "default": False,
        "advanced": True,
        "condition": system.find_executable("pulseaudio"),
        "help": (
            "Set the environment variable PULSE_LATENCY_MSEC=60 "
            "to improve audio quality on some games"
        ),
    },
    {
        "option": "use_us_layout",
        "type": "bool",
        "label": "Switch to US keyboard layout",
        "default": False,
        "advanced": True,
        "help": "Switch to US keyboard qwerty layout while game is running",
    },
    {
        "option": "optimus",
        "type": "choice",
        "default": "off",
        "choices": get_optirun_choices,
        "label": "Optimus launcher (NVIDIA Optimus laptops)",
        "advanced": True,
        "help": (
            "If you have installed the primus or bumblebee packages, "
            "select what launcher will run the game with the command, "
            "activating your NVIDIA graphic chip for high 3D "
            "performance. primusrun normally has better performance, but"
            "optirun/virtualgl works better for more games."
            "Primus VK provide vulkan support under bumblebee."
        ),
    },
    {
        "option": "vk_icd",
        "type": "choice",
        "default": "",
        "choices": get_vk_icd_choices,
        "label": "Vulkan ICD loader",
        "advanced": True,
        "help": (
            "The ICD loader is a library that is placed between a Vulkan "
            "application and any number of Vulkan drivers, in order to support "
            "multiple drivers and the instance-level functionality that works "
            "across these drivers."
        )
    },
    {
        "option": "fps_limit",
        "type": "string",
        "size": "small",
        "label": "Fps limit",
        "advanced": True,
        "condition": bool(system.find_executable("strangle")),
        "help": "Limit the game's fps to desired number",
    },
    {
        "option": "gamemode",
        "type": "bool",
        "default": system.LINUX_SYSTEM.is_feature_supported("GAMEMODE"),
        "condition": system.LINUX_SYSTEM.is_feature_supported("GAMEMODE"),
        "label": "Enable Feral gamemode",
        "help": "Request a set of optimisations be temporarily applied to the host OS",
    },
    {
        "option": "dri_prime",
        "type": "bool",
        "default": display.USE_DRI_PRIME,
        "condition": display.USE_DRI_PRIME,
        "label": "Use discrete graphics",
        "advanced": True,
        "help": (
            "If you have open source graphic drivers (Mesa), selecting this "
            "option will run the game with the 'DRI_PRIME=1' environment variable, "
            "activating your discrete graphic chip for high 3D "
            "performance."
        ),
    },
    {
        "option": "sdl_video_fullscreen",
        "type": "choice",
        "label": "SDL 1.2 Fullscreen Monitor",
        "choices": display.get_output_list,
        "default": "off",
        "advanced": True,
        "help": (
            "Hint SDL 1.2 games to use a specific monitor when going "
            "fullscreen by setting the SDL_VIDEO_FULLSCREEN "
            "environment variable"
        ),
    },
    {
        "option": "display",
        "type": "choice",
        "label": "Turn off monitors except",
        "choices": display.get_output_choices,
        "default": "off",
        "advanced": True,
        "help": (
            "Only keep the selected screen active while the game is "
            "running. \n"
            "This is useful if you have a dual-screen setup, and are \n"
            "having display issues when running a game in fullscreen."
        ),
    },
    {
        "option": "resolution",
        "type": "choice",
        "label": "Switch resolution to",
        "choices": display.get_resolution_choices,
        "default": "off",
        "help": "Switch to this screen resolution while the game is running.",
    },
    {
        "option": "terminal",
        "label": "Run in a terminal",
        "type": "bool",
        "default": False,
        "advanced": True,
        "help": "Run the game in a new terminal window.",
    },
    {
        "option": "terminal_app",
        "label": "Terminal application",
        "type": "choice_with_entry",
        "choices": system.get_terminal_apps,
        "default": system.get_default_terminal(),
        "advanced": True,
        "help": (
            "The terminal emulator to be run with the previous option."
            "Choose from the list of detected terminal apps or enter "
            "the terminal's command or path."
            "Note: Not all terminal emulators are guaranteed to work."
        ),
    },
    {
        "option": "env",
        "type": "mapping",
        "label": "Environment variables",
        "help": "Environment variables loaded at run time",
    },
    {
        "option": "prefix_command",
        "type": "string",
        "label": "Command prefix",
        "advanced": True,
        "help": (
            "Command line instructions to add in front of the game's "
            "execution command."
        ),
    },
    {
        "option": "manual_command",
        "type": "file",
        "label": "Manual command",
        "advanced": True,
        "help": ("Script to execute from the game's contextual menu"),
    },
    {
        "option": "prelaunch_command",
        "type": "file",
        "label": "Pre-launch command",
        "advanced": True,
        "help": "Script to execute before the game starts",
    },
    {
        "option": "prelaunch_wait",
        "type": "bool",
        "label": "Wait for pre-launch command completion",
        "advanced": True,
        "default": False,
        "help": "Run the game only once the pre-launch command has exited",
    },
    {
        "option": "postexit_command",
        "type": "file",
        "label": "Post-exit command",
        "advanced": True,
        "help": "Script to execute when the game exits",
    },
    {
        "option": "include_processes",
        "type": "string",
        "label": "Include processes",
        "advanced": True,
        "help": (
            "What processes to include in process monitoring. "
            "This is to override the built-in exclude list.\n"
            "Space-separated list, processes including spaces "
            "can be wrapped in quotation marks."
        ),
    },
    {
        "option": "exclude_processes",
        "type": "string",
        "label": "Exclude processes",
        "advanced": True,
        "help": (
            "What processes to exclude in process monitoring. "
            "For example background processes that stick around "
            "after the game has been closed.\n"
            "Space-separated list, processes including spaces "
            "can be wrapped in quotation marks."
        ),
    },
    {
        "option": "killswitch",
        "type": "string",
        "label": "Killswitch file",
        "advanced": True,
        "help": (
            "Path to a file which will stop the game when deleted \n"
            "(usually /dev/input/js0 to stop the game on joystick "
            "unplugging)"
        ),
    },
    {
        "option": "xboxdrv",
        "type": "string",
        "label": "xboxdrv config",
        "advanced": True,
        "condition": system.find_executable("xboxdrv"),
        "help": (
            "Command line options for xboxdrv, a driver for XBOX 360 "
            "controllers. Requires the xboxdrv package installed."
        ),
    },
    {
        "option": "sdl_gamecontrollerconfig",
        "type": "string",
        "label": "SDL2 gamepad mapping",
        "advanced": True,
        "help": (
            "SDL_GAMECONTROLLERCONFIG mapping string or path to a custom "
            "gamecontrollerdb.txt file containing mappings."
        ),
    },
    {
        "option": "xephyr",
        "label": "Use Xephyr",
        "type": "choice",
        "choices": (
            ("Off", "off"),
            ("8BPP (256 colors)", "8bpp"),
            ("16BPP (65536 colors)", "16bpp"),
            ("24BPP (16M colors)", "24bpp"),
        ),
        "default": "off",
        "advanced": True,
        "help": "Run program in Xephyr to support 8BPP and 16BPP color modes",
    },
    {
        "option": "xephyr_resolution",
        "type": "string",
        "label": "Xephyr resolution",
        "advanced": True,
        "help": "Screen resolution of the Xephyr server",
    },
    {
        "option": "xephyr_fullscreen",
        "type": "bool",
        "label": "Xephyr Fullscreen",
        "default": True,
        "advanced": True,
        "help": "Open Xephyr in fullscreen (at the desktop resolution)",
    },
]


def with_runner_overrides(runner_slug):
    """Return system options updated with overrides from given runner."""
    options = system_options
    try:
        runner = runners.import_runner(runner_slug)
    except runners.InvalidRunner:
        return options
    if not getattr(runner, "system_options_override"):
        runner = runner()
    if runner.system_options_override:
        opts_dict = OrderedDict((opt["option"], opt) for opt in options)
        for option in runner.system_options_override:
            key = option["option"]
            if opts_dict.get(key):
                opts_dict[key] = opts_dict[key].copy()
                opts_dict[key].update(option)
            else:
                opts_dict[key] = option
        options = [opt for opt in list(opts_dict.values())]
    return options
