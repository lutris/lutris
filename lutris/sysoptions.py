"""Options list for system config."""
# Standard Library
import glob
# pylint: disable=invalid-name
import os
from collections import OrderedDict
from gettext import gettext as _

# Lutris Modules
from lutris import runners
from lutris.discord import DiscordPresence
from lutris.util import system
from lutris.util.display import DISPLAY_MANAGER, SCREEN_SAVER_INHIBITOR, USE_DRI_PRIME

VULKAN_DATA_DIRS = [
    "/usr/local/etc/vulkan",  # standard site-local location
    "/usr/local/share/vulkan",  # standard site-local location
    "/etc/vulkan",  # standard location
    "/usr/share/vulkan",  # standard location
    "/usr/lib/x86_64-linux-gnu/GL/vulkan",  # Flatpak GL extension
    "/usr/lib/i386-linux-gnu/GL/vulkan",  # Flatpak GL32 extension
    "/opt/amdgpu-pro/etc/vulkan"  # AMD GPU Pro - TkG
]


def get_resolution_choices():
    """Return list of available resolutions as label, value tuples
    suitable for inclusion in drop-downs.
    """
    resolutions = DISPLAY_MANAGER.get_resolutions()
    resolution_choices = list(zip(resolutions, resolutions))
    resolution_choices.insert(0, (_("Keep current"), "off"))
    return resolution_choices


def get_output_choices():
    """Return list of outputs for drop-downs"""
    displays = DISPLAY_MANAGER.get_display_names()
    output_choices = list(zip(displays, displays))
    output_choices.insert(0, (_("Off"), "off"))
    output_choices.insert(1, (_("Primary"), "primary"))
    return output_choices


def get_output_list():
    """Return a list of output with their index.
    This is used to indicate to SDL 1.2 which monitor to use.
    """
    choices = [(_("Off"), "off")]
    displays = DISPLAY_MANAGER.get_display_names()
    for index, output in enumerate(displays):
        # Display name can't be used because they might not be in the right order
        # Using DISPLAYS to get the number of connected monitors
        choices.append((output, str(index)))
    return choices


def get_optirun_choices():
    """Return menu choices (label, value) for Optimus"""
    choices = [(_("Off"), "off")]
    if system.find_executable("primusrun"):
        choices.append(("primusrun", "primusrun"))
    if system.find_executable("optirun"):
        choices.append(("optirun/virtualgl", "optirun"))
    if system.find_executable("pvkrun"):
        choices.append(("primus vk", "pvkrun"))
    return choices


def get_vk_icd_choices():
    """Return available Vulkan ICD loaders"""
    choices = [(_("Auto"), "")]

    # Add loaders
    for data_dir in VULKAN_DATA_DIRS:
        path = os.path.join(data_dir, "icd.d", "*.json")
        for loader in glob.glob(path):
            choices.append((os.path.basename(loader), loader))

    return choices


discord_presence = DiscordPresence()

system_options = [  # pylint: disable=invalid-name
    {
        "option": "game_path",
        "type": "directory_chooser",
        "label": _("Default installation folder"),
        "default": os.path.expanduser("~/Games"),
        "scope": ["runner", "system"],
        "help": _("The default folder where you install your games.")
    },
    {
        "option":
        "disable_runtime",
        "type":
        "bool",
        "label":
        _("Disable Lutris Runtime"),
        "default":
        False,
        "help": _("The Lutris Runtime loads some libraries before running the "
                  "game. Which can cause some incompatibilities in some cases. "
                  "Check this option to disable it."),
    },
    {
        "option": "prefer_system_libs",
        "type": "bool",
        "label": _("Prefer system libraries"),
        "default": True,
        "help": _("When the runtime is enabled, prioritize the system libraries"
                  " over the provided ones."),
    },
    {
        "option":
        "reset_desktop",
        "type":
        "bool",
        "label":
        _("Restore resolution on game exit"),
        "default":
        False,
        "help": _("Some games don't restore your screen resolution when \n"
                  "closed or when they crash. This is when this option comes \n"
                  "into play to save your bacon."),
    },
    {
        "option": "single_cpu",
        "type": "bool",
        "label": _("Restrict to single core"),
        "advanced": True,
        "default": False,
        "help": _("Restrict the game to a single CPU core."),
    },
    {
        "option":
        "restore_gamma",
        "type":
        "bool",
        "default":
        False,
        "label":
        _("Restore gamma on game exit"),
        "advanced":
        True,
        "help": _("Some games don't correctly restores gamma on exit, making "
                  "your display too bright. Select this option to correct it."),
    },
    {
        "option": "disable_compositor",
        "label": _("Disable desktop effects"),
        "type": "bool",
        "default": False,
        "advanced": True,
        "help": _("Disable desktop effects while game is running, "
                  "reducing stuttering and increasing performance"),
    },
    {
        "option": "disable_screen_saver",
        "label": _("Disable screen saver"),
        "type": "bool",
        "default": SCREEN_SAVER_INHIBITOR is not None,
        "advanced": False,
        "condition": SCREEN_SAVER_INHIBITOR is not None,
        "help": _("Disable the screen saver while a game is running. "
                  "Requires the screen saver's functionality "
                  "to be exposed over DBus."),
    },
    {
        "option": "reset_pulse",
        "type": "bool",
        "label": _("Reset PulseAudio"),
        "default": False,
        "advanced": True,
        "condition": system.find_executable("pulseaudio"),
        "help": _("Restart PulseAudio before launching the game."),
    },
    {
        "option": "pulse_latency",
        "type": "bool",
        "label": _("Reduce PulseAudio latency"),
        "default": False,
        "advanced": True,
        "condition": system.find_executable("pulseaudio"),
        "help": _("Set the environment variable PULSE_LATENCY_MSEC=60 "
                  "to improve audio quality on some games"),
    },
    {
        "option": "use_us_layout",
        "type": "bool",
        "label": _("Switch to US keyboard layout"),
        "default": False,
        "advanced": True,
        "help": _("Switch to US keyboard qwerty layout while game is running"),
    },
    {
        "option":
        "optimus",
        "type":
        "choice",
        "default":
        "off",
        "choices":
        get_optirun_choices,
        "label":
        _("Optimus launcher (NVIDIA Optimus laptops)"),
        "advanced":
        True,
        "help": _("If you have installed the primus or bumblebee packages, "
                  "select what launcher will run the game with the command, "
                  "activating your NVIDIA graphic chip for high 3D "
                  "performance. primusrun normally has better performance, but"
                  "optirun/virtualgl works better for more games."
                  "Primus VK provide vulkan support under bumblebee."),
    },
    {
        "option": "vk_icd",
        "type": "choice",
        "default": "",
        "choices": get_vk_icd_choices,
        "label": _("Vulkan ICD loader"),
        "advanced": True,
        "help": _("The ICD loader is a library that is placed between a Vulkan "
                  "application and any number of Vulkan drivers, in order to support "
                  "multiple drivers and the instance-level functionality that works "
                  "across these drivers.")
    },
    {
        "option": "mangohud",
        "type": "choice",
        "label": _("FPS counter (MangoHud)"),
        "choices": (
            (_("Disabled"), ""),
            (_("Enabled (Vulkan)"), "vk64"),
            (_("Enabled (OpenGL)"), "gl64"),
            (_("Enabled (OpenGL, 32bit)"), "gl32")
        ),
        "default": "",
        "advanced": False,
        "condition": bool(system.find_executable("mangohud")),
        "help": _("Display the game's FPS + other information. Requires MangoHud to be installed."),
    },
    {
        "option": "fps_limit",
        "type": "string",
        "size": "small",
        "label": _("Fps limit"),
        "advanced": True,
        "condition": bool(system.find_executable("strangle")),
        "help": _("Limit the game's fps to desired number"),
    },
    {
        "option": "aco",
        "type": "bool",
        "label": _("Enable ACO shader compiler"),
        "condition": system.LINUX_SYSTEM.is_feature_supported("ACO"),
        "help": _("Enable ACO shader compiler, improving performance in a lot of games. "
                  "Requires Mesa 19.3 or later.")
    },
    {
        "option": "gamemode",
        "type": "bool",
        "default": system.LINUX_SYSTEM.gamemode_available(),
        "condition": system.LINUX_SYSTEM.gamemode_available,
        "label": _("Enable Feral gamemode"),
        "help": _("Request a set of optimisations be temporarily applied to the host OS"),
    },
    {
        "option":
        "prime",
        "type":
        "bool",
        "default":
        False,
        "condition":
        True,
        "label":
        _("Enable NVIDIA Prime render offload"),
        "help": _("If you have the latest NVIDIA driver and the properly patched xorg-server (see "
                  "https://download.nvidia.com/XFree86/Linux-x86_64/435.17/README/primerenderoffload.html"
                  "), you can launch a game on your NVIDIA GPU by toggling this switch. This will apply "
                  "__NV_PRIME_RENDER_OFFLOAD=1 and "
                  "__GLX_VENDOR_LIBRARY_NAME=nvidia environment variables.")
    },
    {
        "option":
        "dri_prime",
        "type":
        "bool",
        "default":
        USE_DRI_PRIME,
        "condition":
        USE_DRI_PRIME,
        "label":
        _("Use discrete graphics"),
        "advanced":
        True,
        "help": _("If you have open source graphic drivers (Mesa), selecting this "
                  "option will run the game with the 'DRI_PRIME=1' environment variable, "
                  "activating your discrete graphic chip for high 3D "
                  "performance."),
    },
    {
        "option":
        "sdl_video_fullscreen",
        "type":
        "choice",
        "label":
        _("SDL 1.2 Fullscreen Monitor"),
        "choices":
        get_output_list,
        "default":
        "off",
        "advanced":
        True,
        "help": _("Hint SDL 1.2 games to use a specific monitor when going "
                  "fullscreen by setting the SDL_VIDEO_FULLSCREEN "
                  "environment variable"),
    },
    {
        "option":
        "display",
        "type":
        "choice",
        "label":
        _("Turn off monitors except"),
        "choices":
        get_output_choices,
        "default":
        "off",
        "advanced":
        True,
        "help": _("Only keep the selected screen active while the game is "
                  "running. \n"
                  "This is useful if you have a dual-screen setup, and are \n"
                  "having display issues when running a game in fullscreen."),
    },
    {
        "option": "resolution",
        "type": "choice",
        "label": _("Switch resolution to"),
        "choices": get_resolution_choices,
        "default": "off",
        "help": _("Switch to this screen resolution while the game is running."),
    },
    {
        "option": "terminal",
        "label": _("Run in a terminal"),
        "type": "bool",
        "default": False,
        "advanced": True,
        "help": _("Run the game in a new terminal window."),
    },
    {
        "option":
        "terminal_app",
        "label":
        _("Terminal application"),
        "type":
        "choice_with_entry",
        "choices":
        system.get_terminal_apps,
        "default":
        system.get_default_terminal(),
        "advanced":
        True,
        "help": _("The terminal emulator to be run with the previous option."
                  "Choose from the list of detected terminal apps or enter "
                  "the terminal's command or path."
                  "Note: Not all terminal emulators are guaranteed to work."),
    },
    {
        "option": "env",
        "type": "mapping",
        "label": _("Environment variables"),
        "help": _("Environment variables loaded at run time"),
    },
    {
        "option": "prefix_command",
        "type": "string",
        "label": _("Command prefix"),
        "advanced": True,
        "help": _("Command line instructions to add in front of the game's "
                  "execution command."),
    },
    {
        "option": "manual_command",
        "type": "file",
        "label": _("Manual script"),
        "advanced": True,
        "help": _("Script to execute from the game's contextual menu"),
    },
    {
        "option": "prelaunch_command",
        "type": "file",
        "label": _("Pre-launch script"),
        "advanced": True,
        "help": _("Script to execute before the game starts"),
    },
    {
        "option": "prelaunch_wait",
        "type": "bool",
        "label": _("Wait for pre-launch script completion"),
        "advanced": True,
        "default": False,
        "help": _("Run the game only once the pre-launch script has exited"),
    },
    {
        "option": "postexit_command",
        "type": "file",
        "label": _("Post-exit script"),
        "advanced": True,
        "help": _("Script to execute when the game exits"),
    },
    {
        "option":
        "include_processes",
        "type":
        "string",
        "label":
        _("Include processes"),
        "advanced":
        True,
        "help": _("What processes to include in process monitoring. "
                  "This is to override the built-in exclude list.\n"
                  "Space-separated list, processes including spaces "
                  "can be wrapped in quotation marks."),
    },
    {
        "option":
        "exclude_processes",
        "type":
        "string",
        "label":
        _("Exclude processes"),
        "advanced":
        True,
        "help": _("What processes to exclude in process monitoring. "
                  "For example background processes that stick around "
                  "after the game has been closed.\n"
                  "Space-separated list, processes including spaces "
                  "can be wrapped in quotation marks."),
    },
    {
        "option":
        "killswitch",
        "type":
        "string",
        "label":
        _("Killswitch file"),
        "advanced":
        True,
        "help": _("Path to a file which will stop the game when deleted \n"
                  "(usually /dev/input/js0 to stop the game on joystick "
                  "unplugging)"),
    },
    {
        "option":
        "sdl_gamecontrollerconfig",
        "type":
        "string",
        "label":
        _("SDL2 gamepad mapping"),
        "advanced":
        True,
        "help": _("SDL_GAMECONTROLLERCONFIG mapping string or path to a custom "
                  "gamecontrollerdb.txt file containing mappings."),
    },
    {
        "option":
        "xephyr",
        "label":
        _("Use Xephyr"),
        "type":
        "choice",
        "choices": (
            (_("Off"), "off"),
            (_("8BPP (256 colors)"), "8bpp"),
            (_("16BPP (65536 colors)"), "16bpp"),
            (_("24BPP (16M colors)"), "24bpp"),
        ),
        "default":
        "off",
        "advanced":
        True,
        "help":
        _("Run program in Xephyr to support 8BPP and 16BPP color modes"),
    },
    {
        "option": "xephyr_resolution",
        "type": "string",
        "label": _("Xephyr resolution"),
        "advanced": True,
        "help": _("Screen resolution of the Xephyr server"),
    },
    {
        "option": "xephyr_fullscreen",
        "type": "bool",
        "label": _("Xephyr Fullscreen"),
        "default": True,
        "advanced": True,
        "help": _("Open Xephyr in fullscreen (at the desktop resolution)"),
    },
]

discord_options = [
    {
        "option": "discord_rpc_enabled",
        "type": "bool",
        "label": _("Discord Rich Presence"),
        "default": False,
        "condition": discord_presence.available,
        "help": _("Enable status to Discord of this game being played"),
    },
    {
        "option": "discord_show_runner",
        "type": "bool",
        "label": _("Discord Show Runner"),
        "default": True,
        "condition": discord_presence.available,
        "help": _("Embed the runner name in the Discord status"),
    },
    {
        "option": "discord_custom_game_name",
        "type": "string",
        "label": _("Discord Custom Game Name"),
        "condition": discord_presence.available,
        "help": _("Custom name to override with and pass to Discord"),
    },
    {
        "option": "discord_custom_runner_name",
        "type": "string",
        "label": _("Discord Custom Runner Name"),
        "condition": discord_presence.available,
        "help": _("Custom runner name to override with and pass to Discord"),
    },
    {
        "option": "discord_client_id",
        "type": "string",
        "label": _("Discord Client ID"),
        "condition": discord_presence.available,
        "help": _("Custom Discord Client ID for passing status"),
    },
]

if discord_presence.available:
    system_options += discord_options


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
        options = list(opts_dict.values())
    return options
