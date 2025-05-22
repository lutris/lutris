import os
import subprocess
from gettext import gettext as _
from typing import Any, Dict, List, Optional

from lutris import settings
from lutris.config import LutrisConfig
from lutris.exceptions import MissingExecutableError
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.strings import split_arguments

_supported_scale_factors = {
    "hq": ["2", "3"],
    "edge": ["2", "3"],
    "advmame": ["2", "3"],
    "sai": ["2"],
    "supersai": ["2"],
    "supereagle": ["2"],
    "dotmatrix": ["2"],
    "tv2x": ["2"],
}


def _get_opengl_warning(_option_key: str, config: LutrisConfig) -> Optional[str]:
    runner_config = config.runner_config
    if "scaler" in runner_config and "renderer" in runner_config:
        renderer = runner_config["renderer"]
        if renderer and renderer != "software":
            scaler = runner_config["scaler"]
            if scaler and scaler != "normal":
                return _("<b>Warning</b> Scalers may not work with OpenGL rendering.")

    return None


def _get_scale_factor_warning(_option_key: str, config: LutrisConfig) -> Optional[str]:
    """Generate a warning message for when the scaler and scale-factor can't be used together."""
    runner_config = config.runner_config
    if "scaler" in runner_config and "scale-factor" in runner_config:
        scaler = runner_config["scaler"]
        if scaler in _supported_scale_factors:
            scale_factor = runner_config["scale-factor"]
            if scale_factor not in _supported_scale_factors[scaler]:
                return _("<b>Warning</b> The '%s' scaler does not work with a scale factor of %s.") % (
                    scaler,
                    scale_factor,
                )

    return None


class scummvm(Runner):
    description = _("Engine for point-and-click games.")
    human_name = _("ScummVM")
    platforms = [_("Linux")]
    runnable_alone = True
    runner_executable = "scummvm/bin/scummvm"
    flatpak_id = "org.scummvm.ScummVM"
    game_options = [
        {"option": "game_id", "type": "string", "label": _("Game identifier")},
        {"option": "path", "type": "directory", "label": _("Game files location")},
        {
            "option": "args",
            "type": "string",
            "label": _("Arguments"),
            "help": _("Command line arguments used when launching the game"),
        },
    ]

    option_map = {
        "aspect": "--aspect-ratio",
        "subtitles": "--subtitles",
        "fullscreen": "--fullscreen",
        "scaler": "--scaler=%s",
        "scale-factor": "--scale-factor=%s",
        "renderer": "--renderer=%s",
        "render-mode": "--render-mode=%s",
        "stretch-mode": "--stretch-mode=%s",
        "filtering": "--filtering",
        "platform": "--platform=%s",
        "engine-speed": "--engine-speed=%s",
        "talk-speed": "--talkspeed=%s",
        "dimuse-tempo": "--dimuse-tempo=%s",
        "music-tempo": "--tempo=%s",
        "opl-driver": "--opl-driver=%s",
        "output-rate": "--output-rate=%s",
        "music-driver": "--music-driver=%s",
        "multi-midi": "--multi-midi",
        "midi-gain": "--midi-gain=%s",
        "soundfont": "--soundfont=%s",
        "music-volume": "--music-volume=%s",
        "sfx-volume": "--sfx-volume=%s",
        "speech-volume": "--speech-volume=%s",
        "native-mt32": "--native-mt32",
        "enable-gs": "--enable-gs",
        "joystick": "--joystick=%s",
        "language": "--language=%s",
        "alt-intro": "--alt-intro",
        "copy-protection": "--copy-protection",
        "demo-mode": "--demo-mode",
        "debug-level": "--debug-level=%s",
        "debug-flags": "--debug-flags=%s",
    }

    option_empty_map = {"fullscreen": "--no-fullscreen"}

    runner_options = [
        {
            "option": "fullscreen",
            "section": _("Graphics"),
            "label": _("Fullscreen"),
            "type": "bool",
            "default": True,
        },
        {
            "option": "subtitles",
            "section": _("Graphics"),
            "label": _("Enable subtitles"),
            "type": "bool",
            "default": False,
            "help": ("Enable subtitles for games with voice"),
        },
        {
            "option": "aspect",
            "section": _("Graphics"),
            "label": _("Aspect ratio correction"),
            "type": "bool",
            "default": True,
            "help": _(
                "Most games supported by ScummVM were made for VGA "
                "display modes using rectangular pixels. Activating "
                "this option for these games will preserve the 4:3 "
                "aspect ratio they were made for."
            ),
        },
        {
            "option": "scaler",
            "section": _("Graphics"),
            "label": _("Graphic scaler"),
            "type": "choice",
            "default": "normal",
            "choices": [
                ("normal", "normal"),
                ("hq", "hq"),
                ("edge", "edge"),
                ("advmame", "advmame"),
                ("sai", "sai"),
                ("supersai", "supersai"),
                ("supereagle", "supereagle"),
                ("pm", "pm"),
                ("dotmatrix", "dotmatrix"),
                ("tv2x", "tv2x"),
            ],
            "warning": _get_opengl_warning,
            "help": _(
                "The algorithm used to scale up the game's base resolution, resulting in different visual styles. "
            ),
        },
        {
            "option": "scale-factor",
            "section": _("Graphics"),
            "label": _("Scale factor"),
            "type": "choice",
            "default": "3",
            "choices": [
                ("1", "1"),
                ("2", "2"),
                ("3", "3"),
                ("4", "4"),
                ("5", "5"),
            ],
            "help": _(
                "Changes the resolution of the game. "
                "For example, a 2x scale will take a 320x200 "
                "resolution game and scale it up to 640x400. "
            ),
            "warning": _get_scale_factor_warning,
        },
        {
            "option": "renderer",
            "section": _("Graphics"),
            "label": _("Renderer"),
            "type": "choice",
            "choices": [
                (_("Auto"), ""),
                (_("Software"), "software"),
                (_("OpenGL"), "opengl"),
                (_("OpenGL (with shaders)"), "opengl_shaders"),
            ],
            "default": "",
            "advanced": True,
            "help": _("Changes the rendering method used for 3D games."),
        },
        {
            "option": "render-mode",
            "section": _("Graphics"),
            "label": _("Render mode"),
            "type": "choice",
            "choices": [
                (_("Auto"), ""),
                (_("Hercules (Green)"), "hercGreen"),
                (_("Hercules (Amber)"), "hercAmber"),
                (_("CGA"), "cga"),
                (_("EGA"), "ega"),
                (_("VGA"), "vga"),
                (_("Amiga"), "amiga"),
                (_("FM Towns"), "fmtowns"),
                (_("PC-9821"), "pc9821"),
                (_("PC-9801"), "pc9801"),
                (_("Apple IIgs"), "2gs"),
                (_("Atari ST"), "atari"),
                (_("Macintosh"), "macintosh"),
            ],
            "default": "",
            "advanced": True,
            "help": _("Changes the graphics hardware the game will target, if the game supports this."),
        },
        {
            "option": "stretch-mode",
            "section": _("Graphics"),
            "label": _("Stretch mode"),
            "type": "choice",
            "choices": [
                (_("Auto"), ""),
                (_("Center"), "center"),
                (_("Pixel Perfect"), "pixel-perfect"),
                (_("Even Pixels"), "even-pixels"),
                (_("Stretch"), "stretch"),
                (_("Fit"), "fit"),
                (_("Fit (force aspect ratio)"), "fit_force_aspect"),
            ],
            "default": "",
            "advanced": True,
            "help": _("Changes how the game is placed when the window is resized."),
        },
        {
            "option": "filtering",
            "section": _("Graphics"),
            "label": _("Filtering"),
            "type": "bool",
            "help": _(
                "Uses bilinear interpolation instead of nearest neighbor "
                "resampling for the aspect ratio correction and stretch mode."
            ),
            "default": False,
            "advanced": True,
        },
        {
            "option": "datadir",
            "label": _("Data directory"),
            "type": "directory",
            "help": _("Defaults to share/scummvm if unspecified."),
            "advanced": True,
        },
        {
            "option": "platform",
            "type": "string",
            "label": _("Platform"),
            "help": _(
                "Specifes platform of game. Allowed values: 2gs, 3do, acorn, amiga, atari, c64, "
                "fmtowns, nes, mac, pc pc98, pce, segacd, wii, windows"
            ),
            "advanced": True,
        },
        {
            "option": "joystick",
            "type": "string",
            "label": _("Joystick"),
            "help": _("Enables joystick input (default: 0 = first joystick)"),
            "advanced": True,
        },
        {
            "option": "language",
            "type": "string",
            "label": _("Language"),
            "help": _("Selects language (en, de, fr, it, pt, es, jp, zh, kr, se, gb, hb, ru, cz)"),
            "advanced": True,
        },
        {
            "option": "engine-speed",
            "type": "string",
            "label": _("Engine speed"),
            "help": _(
                "Sets frames per second limit (0 - 100) for Grim Fandango or Escape from Monkey Island (default: 60)."
            ),
            "advanced": True,
        },
        {
            "option": "talk-speed",
            "type": "string",
            "label": _("Talk speed"),
            "help": _("Sets talk speed for games (default: 60)"),
            "advanced": True,
        },
        {
            "option": "music-tempo",
            "type": "string",
            "section": _("Audio"),
            "label": _("Music tempo"),
            "help": _("Sets music tempo (in percent, 50-200) for SCUMM games (default: 100)"),
            "advanced": True,
        },
        {
            "option": "dimuse-tempo",
            "type": "string",
            "section": _("Audio"),
            "label": _("Digital iMuse tempo"),
            "help": _("Sets internal Digital iMuse tempo (10 - 100) per second (default: 10)"),
            "advanced": True,
        },
        {
            "option": "music-driver",
            "section": _("Audio"),
            "label": _("Music driver"),
            "type": "choice",
            "choices": [
                ("null", "null"),
                ("auto", "auto"),
                ("seq", "seq"),
                ("sndio", "sndio"),
                ("alsa", "alsa"),
                ("fluidsynth", "fluidsynth"),
                ("mt32", "mt32"),
                ("adlib", "adlib"),
                ("pcspk", "pcspk"),
                ("pcjr", "pcjr"),
                ("cms", "cms"),
                ("timidity", "timidity"),
            ],
            "help": _("Specifies the device ScummVM uses to output audio."),
            "advanced": True,
        },
        {
            "option": "output-rate",
            "section": _("Audio"),
            "label": _("Output rate"),
            "type": "choice",
            "choices": [
                ("11025", "11025"),
                ("22050", "22050"),
                ("44100", "44100"),
            ],
            "help": _("Selects output sample rate in Hz."),
            "advanced": True,
        },
        {
            "option": "opl-driver",
            "section": _("Audio"),
            "label": _("OPL driver"),
            "type": "choice",
            "choices": [
                ("auto", "auto"),
                ("mame", "mame"),
                ("db", "db"),
                ("nuked", "nuked"),
                ("alsa", "alsa"),
                ("op2lpt", "op2lpt"),
                ("op3lpt", "op3lpt"),
                ("rwopl3", "rwopl3"),
            ],
            "help": _(
                "Chooses which emulator is used by ScummVM when the AdLib emulator is chosen as the Preferred device."
            ),
            "advanced": True,
        },
        {
            "option": "music-volume",
            "type": "string",
            "section": _("Audio"),
            "label": _("Music volume"),
            "help": _("Sets the music volume, 0-255 (default: 192)"),
            "advanced": True,
        },
        {
            "option": "sfx-volume",
            "type": "string",
            "section": _("Audio"),
            "label": _("SFX volume"),
            "help": _("Sets the sfx volume, 0-255 (default: 192)"),
            "advanced": True,
        },
        {
            "option": "speech-volume",
            "type": "string",
            "section": _("Audio"),
            "label": _("Speech volume"),
            "help": _("Sets the speech volume, 0-255 (default: 192)"),
            "advanced": True,
        },
        {
            "option": "midi-gain",
            "type": "string",
            "section": _("Audio"),
            "label": _("MIDI gain"),
            "help": _("Sets the gain for MIDI playback. 0-1000 (default: 100)"),
            "advanced": True,
        },
        {
            "option": "soundfont",
            "section": _("Audio"),
            "type": "string",
            "label": _("Soundfont"),
            "help": _("Specifies the path to a soundfont file."),
            "advanced": True,
        },
        {
            "option": "multi-midi",
            "section": _("Audio"),
            "label": _("Mixed AdLib/MIDI mode"),
            "type": "bool",
            "default": False,
            "help": _("Combines MIDI music with AdLib sound effects."),
            "advanced": True,
        },
        {
            "option": "native-mt32",
            "section": _("Audio"),
            "label": _("True Roland MT-32"),
            "type": "bool",
            "default": False,
            "help": _(
                "Tells ScummVM that the MIDI device is an actual Roland MT-32, "
                "LAPC-I, CM-64, CM-32L, CM-500 or other MT-32 device."
            ),
            "advanced": True,
        },
        {
            "option": "enable-gs",
            "section": _("Audio"),
            "label": _("Enable Roland GS"),
            "type": "bool",
            "default": False,
            "help": _(
                "Tells ScummVM that the MIDI device is a GS device that has "
                "an MT-32 map, such as an SC-55, SC-88 or SC-8820."
            ),
            "advanced": True,
        },
        {
            "option": "alt-intro",
            "type": "bool",
            "label": _("Use alternate intro"),
            "help": _("Uses alternative intro for CD versions"),
            "advanced": True,
        },
        {
            "option": "copy-protection",
            "type": "bool",
            "label": _("Copy protection"),
            "help": _("Enables copy protection"),
            "advanced": True,
        },
        {
            "option": "demo-mode",
            "type": "bool",
            "label": _("Demo mode"),
            "help": _("Starts demo mode of Maniac Mansion or The 7th Guest"),
            "advanced": True,
        },
        {
            "option": "debug-level",
            "type": "string",
            "section": _("Debugging"),
            "label": _("Debug level"),
            "help": _("Sets debug verbosity level"),
            "advanced": True,
        },
        {
            "option": "debug-flags",
            "type": "string",
            "section": _("Debugging"),
            "label": _("Debug flags"),
            "help": _("Enables engine specific debug flags"),
            "advanced": True,
        },
    ]

    @property
    def game_path(self):
        return self.game_config.get("path")

    def get_extra_libs(self) -> List[str]:
        """Scummvm runner ships additional libraries, they may be removed in a future version."""
        try:
            base_runner_path = os.path.join(settings.RUNNER_DIR, "scummvm")
            if self.get_executable().startswith(base_runner_path):
                path = os.path.join(settings.RUNNER_DIR, "scummvm/lib")
                if system.path_exists(path):
                    return [path]
        except MissingExecutableError:
            pass

        return []

    def get_command(self) -> List[str]:
        command = super().get_command()
        if not command:
            return []
        if "flatpak" in command[0]:
            return command

        data_dir = self.get_scummvm_data_dir()

        return command + [
            "--extrapath=%s" % data_dir,
            "--themepath=%s" % data_dir,
        ]

    def get_scummvm_data_dir(self) -> str:
        data_dir = self.runner_config.get("datadir")

        if data_dir is None:
            root_dir = os.path.dirname(os.path.dirname(self.get_executable()))
            data_dir = os.path.join(root_dir, "share/scummvm")

        return data_dir

    def get_run_data(self) -> Dict[str, Any]:
        env = self.get_env()
        lib_paths = filter(None, self.get_extra_libs() + [env.get("LD_LIBRARY_PATH")])
        if lib_paths:
            env["LD_LIBRARY_PATH"] = os.pathsep.join(lib_paths)

        return {"env": env, "command": self.get_command()}

    def inject_runner_option(self, command, key, cmdline, cmdline_empty=None):
        value = self.runner_config.get(key)
        if value:
            if "%s" in cmdline:
                command.append(cmdline % value)
            else:
                command.append(cmdline)
        elif cmdline_empty:
            command.append(cmdline_empty)

    def play(self):
        command = self.get_command()
        for option, cmdline in self.option_map.items():
            self.inject_runner_option(command, option, cmdline, self.option_empty_map.get(option))
        command.append("--path=%s" % self.game_path)
        args = self.game_config.get("args") or ""
        for arg in split_arguments(args):
            command.append(arg)
        if self.game_config.get("game_id"):
            command.append(self.game_config.get("game_id"))
        output = {"command": command}

        extra_libs = self.get_extra_libs()
        if extra_libs:
            output["ld_library_path"] = os.pathsep.join(extra_libs)

        return output

    def get_game_list(self) -> List[List[str]]:
        """Return the entire list of games supported by ScummVM."""
        with subprocess.Popen(
            self.get_command() + ["--list-games"], stdout=subprocess.PIPE, encoding="utf-8", universal_newlines=True
        ) as scummvm_process:
            scumm_output = scummvm_process.communicate()[0]
            game_list = str.split(scumm_output, "\n")
        game_array = []
        game_list_start = False
        for game in game_list:
            if game_list_start:
                if len(game) > 1:
                    dir_limit = game.index(" ")
                else:
                    dir_limit = None
                if dir_limit is not None:
                    game_dir = game[0:dir_limit]
                    game_name = game[dir_limit + 1 : len(game)].strip()
                    game_array.append([game_dir, game_name])
            # The actual list is below a separator
            if game.startswith("-----"):
                game_list_start = True
        return game_array
