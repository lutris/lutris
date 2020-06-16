# Standard Library
import os
from gettext import gettext as _

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util.display import DISPLAY_MANAGER


class fsuae(Runner):
    human_name = _("FS-UAE")
    description = _("Amiga emulator")
    platforms = [
        _("Amiga 500"),
        _("Amiga 500+"),
        _("Amiga 600"),
        _("Amiga 1000"),
        _("Amiga 1200"),
        _("Amiga 1200"),
        _("Amiga 4000"),
        _("Amiga CD32"),
        _("Commodore CDTV"),
    ]
    model_choices = [
        (_("Amiga 500"), "A500"),
        (_("Amiga 500+ with 1 MB chip RAM"), "A500+"),
        (_("Amiga 600 with 1 MB chip RAM"), "A600"),
        (_("Amiga 1000 with 512 KB chip RAM"), "A1000"),
        (_("Amiga 1200 with 2 MB chip RAM"), "A1200"),
        (_("Amiga 1200 but with 68020 processor"), "A1200/020"),
        (_("Amiga 4000 with 2 MB chip RAM and a 68040"), "A4000/040"),
        (_("Amiga CD32"), "CD32"),
        (_("Commodore CDTV"), "CDTV"),
    ]
    memory_choices = [
        ("0", "0"),
        ("1 MB", "1024"),
        ("2 MB", "2048"),
        ("4 MB", "4096"),
        ("8 MB", "8192"),
    ]
    flsound_choices = [
        ("0", "0"),
        ("25", "25"),
        ("50", "50"),
        ("75", "75"),
        ("100", "100"),
    ]
    gpucard_choices = [
        ("None", "None"),
        ("UAEGFX", "uaegfx"),
        ("UAEGFX Zorro II", "uaegfx-z2"),
        ("UAEGFX Zorro III", "uaegfx-z3"),
        ("Picasso II Zorro II", "picasso-ii"),
        ("Picasso II+ Zorro II", "picasso-ii+"),
        ("Picasso IV", "picasso-iv"),
        ("Picasso IV Zorro II", "picasso-iv-z2"),
        ("Picasso IV Zorro III", "picasso-iv-z3"),
    ]
    gpumem_choices = [
        ("0", "0"),
        ("1 MB", "1024"),
        ("2 MB", "2048"),
        ("4 MB", "4096"),
        ("8 MB", "8192"),
        ("16 MB", "16384"),
        ("32 MB", "32768"),
        ("64 MB", "65536"),
        ("128 MB", "131072"),
        ("256 MB", "262144"),
    ]
    flspeed_choices = [
        ("Turbo", "0"),
        ("100%", "100"),
        ("200%", "200"),
        ("400%", "400"),
        ("800%", "800"),
    ]
    runner_executable = "fs-uae/fs-uae"
    game_options = [
        {
            "option":
            "main_file",
            "type":
            "file",
            "label":
            _("Boot disk"),
            "default_path":
            "game_path",
            "help": _(
                "The main floppy disk file with the game data. \n"
                "FS-UAE supports floppy images in multiple file formats: "
                "ADF, IPF, DMS are the most common. ADZ (compressed ADF) "
                "and ADFs in zip files are a also supported.\n"
                "Files ending in .hdf will be mounted as hard drives and "
                "ISOs can be used for Amiga CD32 and CDTV models."
            ),
        }, {
            "option": "disks",
            "type": "multiple",
            "label": _("Additionnal floppies"),
            "default_path": "game_path",
            "help": _("The additional floppy disk image(s)."),
        }, {
            "option": "cdrom_image",
            "label": _("CD-Rom image"),
            "type": "file",
            "help": _("CD-ROM image to use on non CD32/CDTV models")
        }
    ]

    runner_options = [
        {
            "option": "model",
            "label": _("Amiga model"),
            "type": "choice",
            "choices": model_choices,
            "default": "A500",
            "help": _("Specify the Amiga model you want to emulate."),
        },
        {
            "option":
            "kickstart_file",
            "label":
            _("Kickstart ROMs location"),
            "type":
            "file",
            "help": _(
                "Choose the folder containing original Amiga kickstart "
                "ROMs. Refer to FS-UAE documentation to find how to "
                "acquire them. Without these, FS-UAE uses a bundled "
                "replacement ROM which is less compatible with Amiga "
                "software."
            ),
        },
        {
            "option": "kickstart_ext_file",
            "label": _("Extended Kickstart location"),
            "type": "file",
            "help": _("Location of extended Kickstart used for CD32"),
        },
        {
            "option": "fmemory",
            "label": _("Fast Memory"),
            "type": "choice",
            "choices": memory_choices,
            "default": "0",
            "help": _("Specify how much Fast Memory the Amiga model should have."),
        },
        {
            "option": "fdvolume",
            "label": _("Floppy Drive Volume"),
            "type": "choice",
            "choices": flsound_choices,
            "default": "0",
            "help": _("Set volume to 0 to disable floppy drive clicks "
                      "when the drive is empty. Max volume is 100.")
        },
        {
            "option":
            "fdspeed",
            "label":
            _("Floppy Drive Speed"),
            "type":
            "choice",
            "choices":
            flspeed_choices,
            "default":
            "100",
            "help": _(
                "Set the speed of the emulated floppy drives, in percent. "
                "For example, you can specify 800 to get an 8x increase in "
                "speed. Use 0 to specify turbo mode. Turbo mode means that "
                "all floppy operations complete immediately. The default is 100 for most models."
            )
        },
        {
            "option":
            "grafixcard",
            "label":
            _("Graphics Card"),
            "type":
            "choice",
            "choices":
            gpucard_choices,
            "default":
            "None",
            "help": _(
                "Use this option to enable a graphics card. This option is none by default, in "
                "which case only chipset graphics (OCS/ECS/AGA) support is available."
            )
        },
        {
            "option":
            "grafixmemory",
            "label":
            _("Graphics Card RAM"),
            "type":
            "choice",
            "choices":
            gpumem_choices,
            "default":
            "0",
            "help": _(
                "Override the amount of graphics memory on the graphics card. The 0 MB option is "
                "not really valid, but exists for user interface reasons."
            )
        },
        {
            "option": "gfx_fullscreen_amiga",
            "label": _("Fullscreen (F12 + s to switch)"),
            "type": "bool",
            "default": False,
        },
        {
            "option": "jitcompiler",
            "label": _("JIT Compiler"),
            "type": "bool",
            "default": False,
        },
        {
            "option": "gamemode",
            "label": _("Feral GameMode"),
            "type": "bool",
            "default": False,
            "help": _("Automatically uses Feral GameMode daemon if available."
                      "set to true to disable the feature.")
        },
        {
            "option": "govwarning",
            "label": _("CPU governor warning"),
            "type": "bool",
            "default": False,
            "help":
            _("Warn if running with a CPU governor other than performance."
              "set to true to disable the warning.")
        },
        {
            "option": "bsdsocket",
            "label": _("UAE bsdsocket.library"),
            "type": "bool",
            "default": False,
        },
        {
            "option": "scanlines",
            "label": _("Scanlines display style"),
            "type": "bool",
            "default": False,
            "help": _("Activates a display filter adding scanlines to imitate "
                      "the displays of yesteryear."),
        },
    ]

    def get_platform(self):
        model = self.runner_config.get("model")
        if model:
            for index, machine in enumerate(self.model_choices):
                if machine[1] == model:
                    return self.platforms[index]
        return ""

    def get_absolute_path(self, path):
        """Return the absolute path for a file"""
        return path if os.path.isabs(path) else os.path.join(self.game_path, path)

    def insert_floppies(self):
        disks = []
        main_disk = self.game_config.get("main_file")
        if main_disk:
            disks.append(main_disk)

        game_disks = self.game_config.get("disks") or []
        for disk in game_disks:
            if disk not in disks:
                disks.append(disk)
        # Make all paths absolute
        disks = [self.get_absolute_path(disk) for disk in disks]
        drives = []
        floppy_images = []
        for drive, disk_path in enumerate(disks):
            disk_param = self.get_disk_param(disk_path)
            drives.append("--%s_%d=%s" % (disk_param, drive, disk_path))
            if disk_param == "floppy_drive":
                floppy_images.append("--floppy_image_%d=%s" % (drive, disk_path))
        cdrom_image = self.game_config.get("cdrom_image")
        if cdrom_image:
            drives.append("--cdrom_drive_0=%s" % self.get_absolute_path(cdrom_image))
        return drives + floppy_images

    def get_disk_param(self, disk_path):
        amiga_model = self.runner_config.get("model")
        if amiga_model in ("CD32", "CDTV"):
            return "cdrom_drive"
        if disk_path.lower().endswith(".hdf"):
            return "hard_drive"
        return "floppy_drive"

    def get_params(self):  # pylint: disable=too-many-branches
        params = []
        model = self.runner_config.get("model")
        fmemory = self.runner_config.get("fmemory")
        fdvolume = self.runner_config.get("fdvolume")
        fdspeed = self.runner_config.get("fdspeed")
        grafixcard = self.runner_config.get("grafixcard")
        grafixmemory = self.runner_config.get("grafixmemory")
        kickstart_file = self.runner_config.get("kickstart_file")
        if kickstart_file:
            params.append("--kickstart_file=%s" % kickstart_file)
        kickstart_ext_file = self.runner_config.get("kickstart_ext_file")
        if kickstart_ext_file:
            params.append("--kickstart_ext_file=%s" % kickstart_ext_file)
        if model:
            params.append("--amiga_model=%s" % model)
        if fmemory:
            params.append("--fast_memory=%s" % fmemory)
        if fdvolume:
            params.append("--floppy_drive_volume=%s" % fdvolume)
        if fdspeed:
            params.append("--floppy_drive_speed=%s" % fdspeed)
        if grafixcard:
            params.append("--graphics_card=%s" % grafixcard)
        if grafixmemory:
            params.append("--graphics_memory=%s" % grafixmemory)
        if self.runner_config.get("gfx_fullscreen_amiga"):
            width = int(DISPLAY_MANAGER.get_current_resolution()[0])
            params.append("--fullscreen")
            # params.append("--fullscreen_mode=fullscreen-window")
            params.append("--fullscreen_mode=fullscreen")
            params.append("--fullscreen_width=%d" % width)
        if self.runner_config.get("jitcompiler"):
            params.append("--jit_compiler=1")
        if self.runner_config.get("bsdsocket"):
            params.append("--bsdsocket_library=1")
        if self.runner_config.get("gamemode"):
            params.append("--game_mode=0")
        if self.runner_config.get("govwarning"):
            params.append("--governor_warning=0")
        if self.runner_config.get("scanlines"):
            params.append("--scanlines=1")
        return params

    def play(self):
        return {"command": [self.get_executable()] + self.get_params() + self.insert_floppies()}
