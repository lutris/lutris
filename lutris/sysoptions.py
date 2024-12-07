"""Options list for system config."""

import os
from collections import OrderedDict
from gettext import gettext as _

from lutris import runners
from lutris.util import linux, system
from lutris.util.display import DISPLAY_MANAGER, SCREEN_SAVER_INHIBITOR, is_compositing_enabled, is_display_x11
from lutris.util.graphics.gpu import GPUS


def get_resolution_choices():
    """Return list of available resolutions as label, value tuples
    suitable for inclusion in drop-downs.
    """
    resolutions = DISPLAY_MANAGER.get_resolutions()
    resolution_choices = list(zip(resolutions, resolutions))
    resolution_choices.insert(0, (_("Keep current"), "off"))
    return resolution_choices


def get_locale_choices():
    """Return list of available locales as label, value tuples
    suitable for inclusion in drop-downs.
    """
    return [
        (_("System"), ""),
        (_("Chinese"), "zh_CN.utf8"),
        (_("Croatian"), "hr_HR.utf8"),
        (_("Dutch"), "nl_NL.utf8"),
        (_("English"), "en_US.utf8"),
        (_("Finnish"), "fi_FI.utf8"),
        (_("French"), "fr_FR.utf"),
        (_("Georgian"), "ka_GE.utf8"),
        (_("German"), "de_DE.utf8"),
        (_("Greek"), "el_GR.utf8"),
        (_("Italian"), "it_IT.utf8"),
        (_("Japanese"), "ja_JP.utf8"),
        (_("Korean"), "ko_KR.utf8"),
        (_("Portuguese (Brazilian)"), "pt_BR.utf8"),
        (_("Polish"), "pl_PL.utf8"),
        (_("Russian"), "ru_RU.utf8"),
        (_("Spanish"), "es_ES.utf8"),
        (_("Turkish"), "tr_TR.utf8"),
    ]


def get_gpu_list():
    choices = [(_("Auto"), "")]
    for card, gpu in GPUS.items():
        choices.append((gpu.short_name, card))
    return choices


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


system_options = [  # pylint: disable=invalid-name
    {
        "section": _("Lutris"),
        "option": "game_path",
        "type": "directory_chooser",
        "label": _("Default installation folder"),
        "warn_if_non_writable_parent": True,
        "default": os.path.expanduser("~/Games"),
        "scope": ["runner", "system"],
        "help": _("The default folder where you install your games."),
    },
    {
        "section": _("Lutris"),
        "option": "disable_runtime",
        "type": "bool",
        "label": _("Disable Lutris Runtime"),
        "default": False,
        "help": _(
            "The Lutris Runtime loads some libraries before running the "
            "game, which can cause some incompatibilities in some cases. "
            "Check this option to disable it."
        ),
    },
    {
        "section": _("Lutris"),
        "option": "prefer_system_libs",
        "type": "bool",
        "label": _("Prefer system libraries"),
        "default": True,
        "help": _("When the runtime is enabled, prioritize the system libraries" " over the provided ones."),
    },
    {
        "section": _("Display"),
        "option": "gpu",
        "type": "choice",
        "label": _("GPU"),
        "choices": get_gpu_list,
        "default": "",
        "condition": lambda: len(GPUS) > 1,
        "help": _("GPU to use to run games"),
    },
    {
        "section": _("Display"),
        "option": "mangohud",
        "type": "bool",
        "label": _("FPS counter (MangoHud)"),
        "default": False,
        "condition": system.can_find_executable("mangohud"),
        "help": _("Display the game's FPS + other information. Requires MangoHud to be installed."),
    },
    {
        "section": _("Display"),
        "option": "reset_desktop",
        "type": "bool",
        "label": _("Restore resolution on game exit"),
        "default": False,
        "visible": is_display_x11,
        "advanced": True,
        "help": _(
            "Some games don't restore your screen resolution when \n"
            "closed or when they crash. This is when this option comes \n"
            "into play to save your bacon."
        ),
    },
    {
        "section": _("Display"),
        "option": "disable_compositor",
        "label": _("Disable desktop effects"),
        "type": "bool",
        "default": False,
        "advanced": True,
        "visible": is_display_x11,
        "condition": is_compositing_enabled,
        "help": _("Disable desktop effects while game is running, " "reducing stuttering and increasing performance"),
    },
    {
        "section": _("Display"),
        "option": "disable_screen_saver",
        "label": _("Disable screen saver"),
        "type": "bool",
        "default": SCREEN_SAVER_INHIBITOR is not None,
        "advanced": True,
        "condition": SCREEN_SAVER_INHIBITOR is not None,
        "help": _(
            "Disable the screen saver while a game is running. "
            "Requires the screen saver's functionality "
            "to be exposed over DBus."
        ),
    },
    {
        "section": _("Display"),
        "option": "sdl_video_fullscreen",
        "type": "choice",
        "label": _("SDL 1.2 Fullscreen Monitor"),
        "choices": get_output_list,
        "default": "off",
        "visible": is_display_x11,
        "advanced": True,
        "help": _(
            "Hint SDL 1.2 games to use a specific monitor when going "
            "fullscreen by setting the SDL_VIDEO_FULLSCREEN "
            "environment variable"
        ),
    },
    {
        "section": _("Display"),
        "option": "display",
        "type": "choice",
        "label": _("Turn off monitors except"),
        "choices": get_output_choices,
        "default": "off",
        "visible": is_display_x11,
        "advanced": True,
        "help": _(
            "Only keep the selected screen active while the game is "
            "running. \n"
            "This is useful if you have a dual-screen setup, and are \n"
            "having display issues when running a game in fullscreen."
        ),
    },
    {
        "section": _("Display"),
        "option": "resolution",
        "type": "choice",
        "label": _("Switch resolution to"),
        "advanced": True,
        "visible": is_display_x11,
        "choices": get_resolution_choices,
        "default": "off",
        "help": _("Switch to this screen resolution while the game is running."),
    },
    {
        "section": _("Gamescope"),
        "option": "gamescope",
        "type": "bool",
        "label": _("Enable Gamescope"),
        "default": False,
        "condition": system.can_find_executable("gamescope") and linux.LINUX_SYSTEM.nvidia_gamescope_support(),
        "help": _("Use gamescope to draw the game window isolated from your desktop.\n" "Toggle fullscreen: Super + F"),
    },
    {
        "section": _("Gamescope"),
        "option": "gamescope_hdr",
        "type": "bool",
        "label": _("Enable HDR (Experimental)"),
        "advanced": False,
        "default": False,
        "condition": bool(system.can_find_executable("gamescope")),
        "help": _("Enable HDR for games that support it.\n" "Requires Plasma 6 and VK_hdr_layer."),
    },
    {
        "section": _("Gamescope"),
        "option": "gamescope_realtime_scheduling",
        "type": "bool",
        "label": _("Realtime Scheduling"),
        "advanced": True,
        "default": False,
        "condition": bool(system.can_find_executable("gamescope")),
        "help": _(
            "Use realtime scheduling.\n"
            "Requires 'CAP_SYS_NICE=eip' capability set on gamescope:\n"
            "\n"
            "    <b>sudo setcap 'CAP_SYS_NICE=eip' $(which gamescope)</b>"
        ),
    },
    {
        "section": _("Gamescope"),
        "option": "gamescope_force_grab_cursor",
        "type": "bool",
        "label": _("Relative Mouse Mode"),
        "advanced": True,
        "default": False,
        "condition": bool(system.can_find_executable("gamescope")),
        "help": _(
            "Always use relative mouse mode instead of flipping\n"
            "dependent on cursor visibility\n"
            "Can help with games where the player's camera faces the floor"
        ),
    },
    {
        "section": _("Gamescope"),
        "option": "gamescope_output_res",
        "type": "choice_with_entry",
        "label": _("Output Resolution"),
        "choices": DISPLAY_MANAGER.get_resolutions,
        "advanced": True,
        "condition": system.can_find_executable("gamescope"),
        "help": _(
            "Set the resolution used by gamescope.\n"
            "Resizing the gamescope window will update these settings.\n"
            "\n"
            "<b>Custom Resolutions:</b> (width)x(height)"
        ),
    },
    {
        "section": _("Gamescope"),
        "option": "gamescope_game_res",
        "type": "choice_with_entry",
        "label": _("Game Resolution"),
        "choices": DISPLAY_MANAGER.get_resolutions,
        "condition": system.can_find_executable("gamescope"),
        "help": _("Set the maximum resolution used by the game.\n" "\n" "<b>Custom Resolutions:</b> (width)x(height)"),
    },
    {
        "section": _("Gamescope"),
        "option": "gamescope_window_mode",
        "label": _("Window Mode"),
        "type": "choice",
        "choices": (
            (_("Fullscreen"), "-f"),
            (_("Windowed"), ""),
            (_("Borderless"), "-b"),
        ),
        "default": "-f",
        "condition": system.can_find_executable("gamescope"),
        "help": _("Run gamescope in fullscreen, windowed or borderless mode\n" "Toggle fullscreen : Super + F"),
    },
    {
        "section": _("Gamescope"),
        "option": "gamescope_fsr_sharpness",
        "label": _("FSR Level"),
        "advanced": True,
        "type": "string",
        "condition": system.can_find_executable("gamescope"),
        "help": _(
            "Use AMD FidelityFX™ Super Resolution 1.0 for upscaling.\n" "Upscaler sharpness from 0 (max) to 20 (min)."
        ),
    },
    {
        "section": _("Gamescope"),
        "option": "gamescope_fps_limiter",
        "label": _("Framerate Limiter"),
        "advanced": False,
        "type": "string",
        "condition": system.can_find_executable("gamescope"),
        "help": _("Set a frame-rate limit for gamescope specified in frames per second."),
    },
    {
        "section": _("Gamescope"),
        "option": "gamescope_flags",
        "label": _("Custom Settings"),
        "advanced": True,
        "type": "string",
        "condition": system.can_find_executable("gamescope"),
        "help": _(
            "Set additional flags for gamescope (if available).\n" "See 'gamescope --help' for a full list of options."
        ),
    },
    {
        "section": _("CPU"),
        "option": "single_cpu",
        "type": "bool",
        "label": _("Restrict number of cores used"),
        "default": False,
        "help": _("Restrict the game to a maximum number of CPU cores."),
    },
    {
        "section": _("CPU"),
        "option": "limit_cpu_count",
        "type": "string",
        "label": _("Restrict number of cores to"),
        "default": "1",
        "help": _("Maximum number of CPU cores to be used, if 'Restrict number of cores used' is turned on."),
    },
    {
        "section": _("CPU"),
        "option": "gamemode",
        "type": "bool",
        "default": linux.LINUX_SYSTEM.gamemode_available(),
        "condition": linux.LINUX_SYSTEM.gamemode_available(),
        "label": _("Enable Feral GameMode"),
        "help": _("Request a set of optimisations be temporarily applied to the host OS"),
    },
    {
        "section": _("Audio"),
        "option": "pulse_latency",
        "type": "bool",
        "label": _("Reduce PulseAudio latency"),
        "default": False,
        "advanced": True,
        "condition": system.can_find_executable("pulseaudio") or system.can_find_executable("pipewire-pulse"),
        "help": _("Set the environment variable PULSE_LATENCY_MSEC=60 " "to improve audio quality on some games"),
    },
    {
        "section": _("Input"),
        "option": "use_us_layout",
        "type": "bool",
        "label": _("Switch to US keyboard layout"),
        "default": False,
        "advanced": True,
        "help": _("Switch to US keyboard QWERTY layout while game is running"),
    },
    {
        "section": _("Input"),
        "option": "antimicro_config",
        "type": "file",
        "label": _("AntiMicroX Profile"),
        "advanced": True,
        "help": _("Path to an AntiMicroX profile file"),
    },
    {
        "section": _("Input"),
        "option": "sdl_gamecontrollerconfig",
        "type": "string",
        "label": _("SDL2 gamepad mapping"),
        "advanced": True,
        "help": _(
            "SDL_GAMECONTROLLERCONFIG mapping string or path to a custom "
            "gamecontrollerdb.txt file containing mappings."
        ),
    },
    {
        "section": _("Text based games"),
        "option": "terminal",
        "label": _("CLI mode"),
        "type": "bool",
        "default": False,
        "advanced": True,
        "help": _(
            "Enable a terminal for text-based games. "
            "Only useful for ASCII based games. May cause issues with graphical games."
        ),
    },
    {
        "section": _("Text based games"),
        "option": "terminal_app",
        "label": _("Text based games emulator"),
        "type": "choice_with_entry",
        "choices": linux.get_terminal_apps,
        "default": linux.get_default_terminal(),
        "advanced": True,
        "help": _(
            "The terminal emulator used with the CLI mode. "
            "Choose from the list of detected terminal apps or enter "
            "the terminal's command or path."
        ),
    },
    {
        "section": _("Game execution"),
        "option": "env",
        "type": "mapping",
        "label": _("Environment variables"),
        "help": _("Environment variables loaded at run time"),
    },
    {
        "section": _("Game execution"),
        "option": "locale",
        "type": "choice_with_entry",
        "label": _("Locale"),
        "choices": (get_locale_choices),
        "default": "",
        "advanced": False,
        "help": _("Can be used to force certain locale for an app. Fixes encoding issues in legacy software."),
    },
    {
        "section": _("Game execution"),
        "option": "prefix_command",
        "type": "string",
        "label": _("Command prefix"),
        "advanced": True,
        "help": _("Command line instructions to add in front of the game's " "execution command."),
    },
    {
        "section": _("Game execution"),
        "option": "manual_command",
        "type": "file",
        "label": _("Manual script"),
        "advanced": True,
        "help": _("Script to execute from the game's contextual menu"),
    },
    {
        "section": _("Game execution"),
        "option": "prelaunch_command",
        "type": "command_line",
        "label": _("Pre-launch script"),
        "advanced": True,
        "help": _("Script to execute before the game starts"),
    },
    {
        "section": _("Game execution"),
        "option": "prelaunch_wait",
        "type": "bool",
        "label": _("Wait for pre-launch script completion"),
        "advanced": True,
        "default": False,
        "help": _("Run the game only once the pre-launch script has exited"),
    },
    {
        "section": _("Game execution"),
        "option": "postexit_command",
        "type": "command_line",
        "label": _("Post-exit script"),
        "advanced": True,
        "help": _("Script to execute when the game exits"),
    },
    {
        "section": _("Game execution"),
        "option": "include_processes",
        "type": "string",
        "label": _("Include processes"),
        "advanced": True,
        "help": _(
            "What processes to include in process monitoring. "
            "This is to override the built-in exclude list.\n"
            "Space-separated list, processes including spaces "
            "can be wrapped in quotation marks."
        ),
    },
    {
        "section": _("Game execution"),
        "option": "exclude_processes",
        "type": "string",
        "label": _("Exclude processes"),
        "advanced": True,
        "help": _(
            "What processes to exclude in process monitoring. "
            "For example background processes that stick around "
            "after the game has been closed.\n"
            "Space-separated list, processes including spaces "
            "can be wrapped in quotation marks."
        ),
    },
    {
        "section": _("Game execution"),
        "option": "killswitch",
        "type": "string",
        "label": _("Killswitch file"),
        "advanced": True,
        "help": _(
            "Path to a file which will stop the game when deleted \n"
            "(usually /dev/input/js0 to stop the game on joystick "
            "unplugging)"
        ),
    },
    {
        "section": _("Xephyr (Deprecated, use Gamescope)"),
        "option": "xephyr",
        "label": _("Use Xephyr"),
        "type": "choice",
        "choices": (
            (_("Off"), "off"),
            (_("8BPP (256 colors)"), "8bpp"),
            (_("16BPP (65536 colors)"), "16bpp"),
            (_("24BPP (16M colors)"), "24bpp"),
        ),
        "default": "off",
        "visible": is_display_x11,
        "advanced": True,
        "help": _("Run program in Xephyr to support 8BPP and 16BPP color modes"),
    },
    {
        "section": _("Xephyr (Deprecated, use Gamescope)"),
        "option": "xephyr_resolution",
        "type": "string",
        "label": _("Xephyr resolution"),
        "visible": is_display_x11,
        "advanced": True,
        "help": _("Screen resolution of the Xephyr server"),
    },
    {
        "section": _("Xephyr (Deprecated, use Gamescope)"),
        "option": "xephyr_fullscreen",
        "type": "bool",
        "label": _("Xephyr Fullscreen"),
        "default": True,
        "visible": is_display_x11,
        "advanced": True,
        "help": _("Open Xephyr in fullscreen (at the desktop resolution)"),
    },
]


def with_runner_overrides(runner_slug):
    """Return system options updated with overrides from given runner."""
    options = system_options
    try:
        runner = runners.import_runner(runner_slug)
    except runners.InvalidRunnerError:
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
