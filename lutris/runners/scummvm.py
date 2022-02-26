# Standard Library
import os
import subprocess
from gettext import gettext as _

# Lutris Modules
from lutris import settings
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.strings import split_arguments


class scummvm(Runner):
    description = _("Engine for point-and-click games.")
    human_name = _("ScummVM")
    platforms = [_("Linux")]
    runnable_alone = True
    runner_executable = "scummvm/bin/scummvm"
    game_options = [
        {
            "option": "game_id",
            "type": "string",
            "label": _("Game identifier")
        },
        {
            "option": "path",
            "type": "directory_chooser",
            "label": _("Game files location")
        },
        {
            "option": "args",
            "type": "string",
            "label": _("Arguments"),
            "help": _("Command line arguments used when launching the game"),
        },
    ]
    runner_options = [
        {
            "option": "fullscreen",
            "label": _("Fullscreen"),
            "type": "bool",
            "default": True,
        },
        {
            "option": "subtitles",
            "label": _("Enable subtitles (if the game has voice)"),
            "type": "bool",
            "default": False,
        },
        {
            "option": "aspect",
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
            "option": "gfx-mode",
            "label": _("Graphic scaler"),
            "type": "choice",
            "default": "3x",
            "choices": [
                ("1x", "1x"),
                ("2x", "2x"),
                ("3x", "3x"),
                ("hq2x", "hq2x"),
                ("hq3x", "hq3x"),
                ("advmame2x", "advmame2x"),
                ("advmame3x", "advmame3x"),
                ("2xsai", "2xsai"),
                ("super2xsai", "super2xsai"),
                ("supereagle", "supereagle"),
                ("tv2x", "tv2x"),
                ("dotmatrix", "dotmatrix"),
            ],
            "help":
            _("The algorithm used to scale up the game's base "
              "resolution, resulting in different visual styles. "),
        },
        {
            "option": "scaler-factor",
            "label": _("Scaler factor"),
            "type": "choice",
            "default": "3",
            "choices": [
                ("1", "1"),
                ("2", "2"),
                ("3", "3"),
                ("4", "4"),
                ("5", "5"),
            ],
            "help":
            _("Changes the resolution of the game. "
              "For example, a 2x scaler will take a 320x200 "
              "resolution game and scale it up to 640x400. "),
        },
        {
            "option": "render-mode",
            "label": _("Render mode"),
            "type": "choice",
            "default": "default",
            "choices": [
                ("default", "default"),
                ("hercGreen", "hercGreen"),
                ("hercAmber", "hercAmber"),
                ("cga", "cga"),
                ("ega", "ega"),
                ("vga", "vga"),
                ("amiga", "amiga"),
                ("fmtowns", "fmtowns"),
                ("pc9821", "pc9821"),
                ("pc9801", "pc9801"),
                ("2gs", "2gs"),
                ("atari", "atari"),
                ("macintosh", "macintosh"),
            ],
            "advanced": True,
            "help": _("Changes how the game is rendered. "),
        },
        {
            "option": "filtering",
            "label": _("Filtering"),
            "type": "bool",
            "help": _("Uses bilinear interpolation instead of nearest neighbor resampling for the aspect ratio correction and stretch mode."),
            "default": False,
            "advanced": True,
        },
        {
            "option": "datadir",
            "label": _("Data directory"),
            "type": "directory_chooser",
            "help": _("Defaults to share/scummvm if unspecified."),
            "advanced": True,
        },
        {
            "option": "platform",
            "type": "string",
            "label": _("Platform"),
            "help": _("Specifes platform of game. Allowed values: 2gs, 3do, acorn, amiga, atari, c64, fmtowns, nes, mac, pc pc98, pce, segacd, wii, windows"),
            "advanced": True,
        },
        {
            "option": "opl-driver",
            "label": _("OPL driver"),
            "type": "choice",
            "default": "auto",
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
            "help": _("Chooses which emulator is used by ScummVM when the AdLib emulator is chosen as the Preferred device."),
            "advanced": True,
        },
        {
            "option": "output-rate",
            "label": _("Output rate"),
            "type": "choice",
            "default": "44100",
            "choices": [
                ("11025", "11025"),
                ("22050", "22050"),
                ("44100", "44100"),
            ],
            "help": _("Selects output sample rate in Hz."),
            "advanced": True,
        },
        {
            "option": "music-driver",
            "label": _("Music driver"),
            "type": "choice",
            "default": "auto",
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
            "option": "multi-midi",
            "label": _("Mixed AdLib/MIDI mode"),
            "type": "bool",
            "default": False,
            "help": _("Combines MIDI music with AdLib sound effects."),
            "advanced": True,
        },
        {
            "option": "midi-gain",
            "type": "string",
            "label": _("MIDI gain"),
            "help": _("Sets the gain for MIDI playback. 0-1000 (default: 100)"),
            "advanced": True,
        },
        {
            "option": "soundfont",
            "type": "string",
            "label": _("Soundfont"),
            "help": _("Specifies the path to a soundfont file."),
            "advanced": True,
        },
        {
            "option": "music-volume",
            "type": "string",
            "label": _("Music volume"),
            "help": _("Sets the music volume, 0-255 (default: 192)"),
            "advanced": True,
        },
        {
            "option": "native-mt32",
            "label": _("True Roland MT-32"),
            "type": "bool",
            "default": False,
            "help": _("Tells ScummVM that the MIDI device is an actual Roland MT-32, LAPC-I, CM-64, CM-32L, CM-500 or other MT-32 device."),
            "advanced": True,
        },
        {
            "option": "enable-gs",
            "label": _("Enable Roland GS"),
            "type": "bool",
            "default": True,
            "help": _("Tells ScummVM that the MIDI device is a GS device that has an MT-32 map, such as an SC-55, SC-88 or SC-8820."),
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
    ]

    @property
    def game_path(self):
        return self.game_config.get("path")

    @property
    def libs_dir(self):
        path = os.path.join(settings.RUNNER_DIR, "scummvm/lib")
        return path if system.path_exists(path) else ""

    def get_command(self):
        return [
            self.get_executable(),
            "--extrapath=%s" % self.get_scummvm_data_dir(),
            "--themepath=%s" % self.get_scummvm_data_dir(),
        ]

    def get_scummvm_data_dir(self):
        data_dir = self.runner_config.get("datadir")

        if data_dir is None:
            root_dir = os.path.dirname(os.path.dirname(self.get_executable()))
            data_dir = os.path.join(root_dir, "share/scummvm")

        return data_dir

    def get_run_data(self):
        env = self.get_env()
        env["LD_LIBRARY_PATH"] = os.pathsep.join(filter(None, [
            self.libs_dir,
            env.get("LD_LIBRARY_PATH")]))
        return {"env": env, "command": self.get_command()}

    def play(self):
        command = self.get_command()

        # Options
        if self.runner_config.get("aspect"):
            command.append("--aspect-ratio")

        if self.runner_config.get("subtitles"):
            command.append("--subtitles")

        if self.runner_config.get("fullscreen"):
            command.append("--fullscreen")
        else:
            command.append("--no-fullscreen")

        mode = self.runner_config.get("gfx-mode")
        if mode:
            command.append("--gfx-mode=%s" % mode)

        scalefactor = self.runner_config.get("scale-factor")
        if scalefactor:
            command.append("--scale-factor=%s" % scalefactor)

        rendermode = self.runner_config.get("render-mode")
        if rendermode:
            command.append("--render-mode=%s" % rendermode)

        if self.runner_config.get("filtering"):
            command.append("--filtering")

        platform = self.runner_config.get("platform")
        if platform:
            command.append("--platform=%s" % platform)

        opldriver = self.runner_config.get("opl-driver")
        if opldriver:
            command.append("--opl-driver=%s" % opldriver)

        outputrate = self.runner_config.get("output-rate")
        if outputrate:
            command.append("--output-rate=%s" % outputrate)

        musicdriver = self.runner_config.get("music-driver")
        if musicdriver:
            command.append("--music-driver=%s" % musicdriver)

        if self.runner_config.get("multi-midi"):
            command.append("--multi-midi")

        midigain = self.runner_config.get("midi-gain")
        if midigain:
            command.append("--midi-gain=%s" % midigain)

        soundfont = self.runner_config.get("soundfont")
        if soundfont:
            command.append("--soundfont=%s" % soundfont)

        music-volume = self.runner_config.get("music-volume")
        if music-volume:
            command.append("--music-volume=%s" % music-volume)

        if self.runner_config.get("native-mt32"):
            command.append("--native-mt32")

        if self.runner_config.get("enable-gs"):
            command.append("--enable-gs")

        joystick = self.runner_config.get("joystick")
        if joystick:
            command.append("--joystick=%s" % joystick)

        language = self.runner_config.get("language")
        if language:
            command.append("--language=%s" % language)

        # /Options
        command.append("--path=%s" % self.game_path)
        args = self.game_config.get("args") or ""
        for arg in split_arguments(args):
            command.append(arg)
        command.append(self.game_config.get("game_id"))
        launch_info = {"command": command, "ld_library_path": self.libs_dir}

        return launch_info

    def get_game_list(self):
        """Return the entire list of games supported by ScummVM."""
        with subprocess.Popen([self.get_executable(), "--list-games"],
                              stdout=subprocess.PIPE, encoding="utf-8", universal_newlines=True) as scummvm_process:
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
                    game_name = game[dir_limit + 1:len(game)].strip()
                    game_array.append([game_dir, game_name])
            # The actual list is below a separator
            if game.startswith("-----"):
                game_list_start = True
        return game_array
