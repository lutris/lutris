import os
from collections import defaultdict
from gettext import gettext as _

from lutris import settings
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.display import DISPLAY_MANAGER

AMIGAS = {
    "A500": {
        "name": _("Amiga 500"),
        "bios_sha1": [
            "891e9a547772fe0c6c19b610baf8bc4ea7fcb785",
            "c39bd9094d4e5f4e28c1411f3086950406062e87",
            "90933936cce43ca9bc6bf375662c076b27e3c458",
        ],
    },
    "A500+": {"name": _("Amiga 500+"), "bios_sha1": ["c5839f5cb98a7a8947065c3ed2f14f5f42e334a1"]},
    "A600": {"name": _("Amiga 600"), "bios_sha1": ["02843c4253bbd29aba535b0aa3bd9a85034ecde4"]},
    "A1200": {"name": _("Amiga 1200"), "bios_sha1": ["e21545723fe8374e91342617604f1b3d703094f1"]},
    "A3000": {"name": _("Amiga 3000"), "bios_sha1": ["f8e210d72b4c4853e0c9b85d223ba20e3d1b36ee"]},
    "A4000": {
        "name": _("Amiga 4000"),
        "bios_sha1": ["5fe04842d04a489720f0f4bb0e46948199406f49", "c3c481160866e60d085e436a24db3617ff60b5f9"],
    },
    "A1000": {"name": _("Amiga 1000"), "bios_sha1": ["11f9e62cf299f72184835b7b2a70a16333fc0d88"]},
    "CD32": {
        "name": _("Amiga CD32"),
        "bios_sha1": ["3525be8887f79b5929e017b42380a79edfee542d"],
        "bios_ext_sha1": ["5bef3d628ce59cc02a66e6e4ae0da48f60e78f7f"],
    },
    "CDTV": {
        "name": _("Commodore CDTV"),
        "bios_sha1": [
            "891e9a547772fe0c6c19b610baf8bc4ea7fcb785",
            "c39bd9094d4e5f4e28c1411f3086950406062e87",
            "90933936cce43ca9bc6bf375662c076b27e3c458",
        ],
        "bios_ext_sha1": ["7ba40ffa17e500ed9fed041f3424bd81d9c907be"],
    },
}


def get_bios_hashes():
    """Return mappings of sha1 hashes to Amiga models
    The first mapping contains the kickstarts and the second one, the extensions (for CD32/CDTV)
    """
    hashes = defaultdict(list)
    ext_hashes = defaultdict(list)
    for model, model_def in AMIGAS.items():
        for sha1_hash in model_def["bios_sha1"]:
            hashes[sha1_hash].append(model)
        if "bios_ext_sha1" in model_def:
            for sha1_hash in model_def["bios_ext_sha1"]:
                ext_hashes[sha1_hash].append(model)
    return hashes, ext_hashes


def scan_dir_for_bios(path):
    """Return a tuple of mappings of Amiga models and their corresponding kickstart file.

    Kickstart files must reside in `path`
    The first mapping contains the kickstarts and the second one, the extensions (for CD32/CDTV)
    """
    bios_sizes = [262144, 524288]
    hashes, ext_hashes = get_bios_hashes()
    found_bios = {}
    found_ext = {}
    incomplete_bios = []
    for file_name in os.listdir(path):
        abs_path = os.path.join(path, file_name)
        file_size = os.path.getsize(abs_path)
        if file_size not in bios_sizes:
            continue
        checksum = system.get_file_checksum(abs_path, "sha1")
        if checksum in hashes:
            for model in hashes[checksum]:
                found_bios[model] = abs_path
        if checksum in ext_hashes:
            for model in ext_hashes[checksum]:
                found_ext[model] = abs_path
    for model in found_bios:
        if "bios_ext_sha1" in AMIGAS[model] and model not in found_ext:
            incomplete_bios.append(model)
    found_bios = {k: v for k, v in found_bios.items() if k not in incomplete_bios}
    return found_bios, found_ext


class fsuae(Runner):
    human_name = _("FS-UAE")
    description = _("Amiga emulator")
    flatpak_id = "net.fsuae.FS-UAE"
    platforms = [
        AMIGAS["A500"]["name"],
        AMIGAS["A500+"]["name"],
        AMIGAS["A600"]["name"],
        AMIGAS["A1200"]["name"],
        AMIGAS["A3000"]["name"],
        AMIGAS["A4000"]["name"],
        AMIGAS["A1000"]["name"],
        AMIGAS["CD32"]["name"],
        AMIGAS["CDTV"]["name"],
    ]

    model_choices = [(model["name"], key) for key, model in AMIGAS.items()]

    cpumodel_choices = [
        (_("68000"), "68000"),
        (_("68010"), "68010"),
        (_("68020 with 24-bit addressing"), "68EC020"),
        (_("68020"), "68020"),
        (_("68030 without internal MMU"), "68EC030"),
        (_("68030"), "68030"),
        (_("68040 without internal FPU and MMU"), "68EC040"),
        (_("68040 without internal FPU"), "68LC040"),
        (_("68040 without internal MMU"), "68040-NOMMU"),
        (_("68040"), "68040"),
        (_("68060 without internal FPU and MMU"), "68EC060"),
        (_("68060 without internal FPU"), "68LC060"),
        (_("68060 without internal MMU"), "68060-NOMMU"),
        (_("68060"), "68060"),
        (_("Auto"), "auto"),
    ]
    memory_choices = [
        (_("0"), "0"),
        (_("1 MB"), "1024"),
        (_("2 MB"), "2048"),
        (_("4 MB"), "4096"),
        (_("8 MB"), "8192"),
    ]
    zorroiii_choices = [
        (_("0"), "0"),
        (_("1 MB"), "1024"),
        (_("2 MB"), "2048"),
        (_("4 MB"), "4096"),
        (_("8 MB"), "8192"),
        (_("16 MB"), "16384"),
        (_("32 MB"), "32768"),
        (_("64 MB"), "65536"),
        (_("128 MB"), "131072"),
        (_("256 MB"), "262144"),
        (_("384 MB"), "393216"),
        (_("512 MB"), "524288"),
        (_("768 MB"), "786432"),
        (_("1 GB"), "1048576"),
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
        (_("0"), "0"),
        (_("1 MB"), "1024"),
        (_("2 MB"), "2048"),
        (_("4 MB"), "4096"),
        (_("8 MB"), "8192"),
        (_("16 MB"), "16384"),
        (_("32 MB"), "32768"),
        (_("64 MB"), "65536"),
        (_("128 MB"), "131072"),
        (_("256 MB"), "262144"),
    ]
    flspeed_choices = [
        (_("Turbo"), "0"),
        ("100%", "100"),
        ("200%", "200"),
        ("400%", "400"),
        ("800%", "800"),
    ]
    runner_executable = "fs-uae/fs-uae"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("Boot disk"),
            "default_path": "game_path",
            "help": _(
                "The main floppy disk file with the game data. \n"
                "FS-UAE supports floppy images in multiple file formats: "
                "ADF, IPF, DMS are the most common. ADZ (compressed ADF) "
                "and ADFs in zip files are a also supported.\n"
                "Files ending in .hdf will be mounted as hard drives and "
                "ISOs can be used for Amiga CD32 and CDTV models."
            ),
        },
        {
            "option": "disks",
            "section": _("Media"),
            "type": "multiple_file",
            "label": _("Additional floppies"),
            "default_path": "game_path",
            "help": _("The additional floppy disk image(s)."),
        },
        {
            "option": "cdrom_image",
            "section": _("Media"),
            "label": _("CD-ROM image"),
            "type": "file",
            "help": _("CD-ROM image to use on non CD32/CDTV models"),
        },
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
            "option": "kickstart_file",
            "section": _("Kickstart"),
            "label": _("Kickstart ROMs location"),
            "type": "file",
            "help": _(
                "Choose the folder containing original Amiga Kickstart "
                "ROMs. Refer to FS-UAE documentation to find how to "
                "acquire them. Without these, FS-UAE uses a bundled "
                "replacement ROM which is less compatible with Amiga "
                "software."
            ),
        },
        {
            "option": "kickstart_ext_file",
            "section": _("Kickstart"),
            "label": _("Extended Kickstart location"),
            "type": "file",
            "help": _("Location of extended Kickstart used for CD32"),
        },
        {
            "option": "gfx_fullscreen_amiga",
            "section": _("Graphics"),
            "label": _("Fullscreen (F12 + F to switch)"),
            "type": "bool",
            "default": False,
        },
        {
            "option": "scanlines",
            "section": _("Graphics"),
            "label": _("Scanlines display style"),
            "type": "bool",
            "default": False,
            "help": _("Activates a display filter adding scanlines to imitate the displays of yesteryear."),
        },
        {
            "option": "grafixcard",
            "section": _("Graphics"),
            "label": _("Graphics Card"),
            "type": "choice",
            "choices": gpucard_choices,
            "default": "None",
            "advanced": True,
            "help": _(
                "Use this option to enable a graphics card. This option is none by default, in "
                "which case only chipset graphics (OCS/ECS/AGA) support is available."
            ),
        },
        {
            "option": "grafixmemory",
            "section": _("Graphics"),
            "label": _("Graphics Card RAM"),
            "type": "choice",
            "choices": gpumem_choices,
            "default": "0",
            "advanced": True,
            "help": _(
                "Override the amount of graphics memory on the graphics card. The 0 MB option is "
                "not really valid, but exists for user interface reasons."
            ),
        },
        {
            "option": "cpumodel",
            "label": _("CPU"),
            "type": "choice",
            "choices": cpumodel_choices,
            "default": "auto",
            "advanced": True,
            "help": _(
                "Use this option to override the CPU model in the emulated Amiga. All Amiga "
                "models imply a default CPU model, so you only need to use this option if you "
                "want to use another CPU."
            ),
        },
        {
            "option": "fmemory",
            "label": _("Fast Memory"),
            "type": "choice",
            "choices": memory_choices,
            "default": "0",
            "advanced": True,
            "help": _("Specify how much Fast Memory the Amiga model should have."),
        },
        {
            "option": "ziiimem",
            "label": _("Zorro III RAM"),
            "type": "choice",
            "choices": zorroiii_choices,
            "default": "0",
            "advanced": True,
            "help": _(
                "Override the amount of Zorro III Fast memory, specified in KB. Must be a "
                "multiple of 1024. The default value depends on [amiga_model]. Requires a "
                "processor with 32-bit address bus, (use for example the A1200/020 model)."
            ),
        },
        {
            "option": "fdvolume",
            "section": _("Media"),
            "label": _("Floppy Drive Volume"),
            "type": "choice",
            "choices": flsound_choices,
            "default": "0",
            "advanced": True,
            "help": _("Set volume to 0 to disable floppy drive clicks when the drive is empty. Max volume is 100."),
        },
        {
            "option": "fdspeed",
            "section": _("Media"),
            "label": _("Floppy Drive Speed"),
            "type": "choice",
            "choices": flspeed_choices,
            "default": "100",
            "advanced": True,
            "help": _(
                "Set the speed of the emulated floppy drives, in percent. "
                "For example, you can specify 800 to get an 8x increase in "
                "speed. Use 0 to specify turbo mode. Turbo mode means that "
                "all floppy operations complete immediately. The default is 100 for most models."
            ),
        },
        {
            "option": "jitcompiler",
            "label": _("JIT Compiler"),
            "type": "bool",
            "default": False,
            "advanced": True,
        },
        {
            "option": "gamemode",
            "label": _("Feral GameMode"),
            "type": "bool",
            "default": False,
            "advanced": True,
            "help": _("Automatically uses Feral GameMode daemon if available. Set to true to disable the feature."),
        },
        {
            "option": "govwarning",
            "label": _("CPU governor warning"),
            "type": "bool",
            "default": False,
            "advanced": True,
            "help": _(
                "Warn if running with a CPU governor other than performance. Set to true to disable the warning."
            ),
        },
        {
            "option": "bsdsocket",
            "label": _("UAE bsdsocket.library"),
            "type": "bool",
            "default": False,
            "advanced": True,
        },
    ]

    @property
    def directory(self):
        return os.path.join(settings.RUNNER_DIR, "fs-uae")

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
        option_params = {
            "kickstart_file": "--kickstart_file=%s",
            "kickstart_ext_file": "--kickstart_ext_file=%s",
            "model": "--amiga_model=%s",
            "cpumodel": "--cpu=%s",
            "fmemory": "--fast_memory=%s",
            "ziiimem": "--zorro_iii_memory=%s",
            "fdvolume": "--floppy_drive_volume=%s",
            "fdspeed": "--floppy_drive_speed=%s",
            "grafixcard": "--graphics_card=%s",
            "grafixmemory": "--graphics_memory=%s",
        }
        for option, param in option_params.items():
            option_value = self.runner_config.get(option)
            if option_value:
                params.append(param % option_value)

        if self.runner_config.get("gfx_fullscreen_amiga"):
            width = DISPLAY_MANAGER.get_current_resolution()[0]
            params.append("--fullscreen")
            # params.append("--fullscreen_mode=fullscreen-window")
            params.append("--fullscreen_mode=fullscreen")
            params.append("--fullscreen_width=%s" % width)
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
        return {"command": self.get_command() + self.get_params() + self.insert_floppies()}
