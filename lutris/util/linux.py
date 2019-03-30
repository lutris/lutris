"""Linux specific platform code"""
import os
import shutil
import sys
import json
import platform
import resource
import subprocess
from collections import defaultdict
from lutris.vendor.distro import linux_distribution
from lutris.util.graphics import drivers
from lutris.util.graphics import glxinfo
from lutris.util.log import logger

SYSTEM_COMPONENTS = {
    "COMMANDS": [
        "xrandr",
        "fuser",
        "glxinfo",
        "vulkaninfo",
        "optirun",
        "primusrun",
        "pvkrun",
        "xboxdrv",
        "pulseaudio",
        "lsi-steam",
        "fuser",
        "7z",
        "gtk-update-icon-cache",
        "lspci",
        "xgamma",
        "ldconfig",
        "strangle",
        "Xephyr",
        "nvidia-smi",
        "wine",
        "fluidsynth",
    ],
    "TERMINALS": [
        "xterm",
        "gnome-terminal",
        "konsole",
        "xfce4-terminal",
        "pantheon-terminal",
        "terminator",
        "mate-terminal",
        "urxvt",
        "cool-retro-term",
        "Eterm",
        "guake",
        "lilyterm",
        "lxterminal",
        "roxterm",
        "rxvt",
        "aterm",
        "sakura",
        "st",
        "terminology",
        "termite",
        "tilix",
        "wterm",
        "kitty",
        "yuakuake",
        "qterminal",
    ],
    "LIBRARIES": {
        "OPENGL": [
            "libGL.so.1",
        ],
        "VULKAN": [
            "libvulkan.so.1",
        ],
        "WINE": [
            "libsqlite3.so.0"
        ],
        "RADEON": [
            "libvulkan_radeon.so"
        ],
        "GAMEMODE": [
            "libgamemodeauto.so"
        ]
    }
}


class LinuxSystem:
    """Global cache for system commands"""
    _cache = {}

    #lib_folders = [
    #    ('/lib', '/lib64'),
    #    ('/lib32', '/lib64'),
    #    ('/usr/lib', '/usr/lib64'),
    #    ('/usr/lib32', '/usr/lib64'),
    #    ('/lib/i386-linux-gnu', '/lib/x86_64-linux-gnu'),
    #    ('/usr/lib/i386-linux-gnu', '/usr/lib/x86_64-linux-gnu'),
    #]
    soundfont_folders = [
        '/usr/share/sounds/sf2',
        '/usr/share/soundfonts',
    ]

    recommended_no_file_open = 524288
    required_components = ["OPENGL"]
    optional_components = ["VULKAN", "WINE", "GAMEMODE"]

    def __init__(self):
        for key in ("COMMANDS", "TERMINALS"):
            self._cache[key] = {}
            for command in SYSTEM_COMPONENTS[key]:
                command_path = shutil.which(command)
                if not command_path:
                    command_path = self.get_sbin_path(command)
                if command_path:
                    self._cache[key][command] = command_path

        # Detect if system is 64bit capable
        self.is_64_bit = sys.maxsize > 2 ** 32
        self.arch = self.get_arch()

        self.populate_libraries()
        self.populate_sound_fonts()
        self.soft_limit, self.hard_limit = self.get_file_limits()
        self.glxinfo = self.get_glxinfo()

    @staticmethod
    def get_sbin_path(command):
        """Some distributions don't put sbin directories in $PATH"""
        path_candidates = ["/sbin", "/usr/sbin"]
        for candidate in path_candidates:
            command_path = os.path.join(candidate, command)
            if os.path.exists(command_path):
                return command_path

    @staticmethod
    def get_file_limits():
        return resource.getrlimit(resource.RLIMIT_NOFILE)

    def has_enough_file_descriptors(self):
        return self.hard_limit >= self.recommended_no_file_open

    @staticmethod
    def get_cpus():
        """Parse the output of /proc/cpuinfo"""
        cpus = [{}]
        cpu_index = 0
        with open("/proc/cpuinfo") as cpuinfo:
            for line in cpuinfo.readlines():
                if not line.strip():
                    cpu_index += 1
                    cpus.append({})
                    continue
                key, value = line.split(":", 1)
                cpus[cpu_index][key.strip()] = value.strip()
        return [cpu for cpu in cpus if cpu]

    @staticmethod
    def get_drives():
        """Return a list of drives with their filesystems"""
        try:
            output = subprocess.check_output(["lsblk", "-f", "--json"]).decode()
        except subprocess.CalledProcessError as ex:
            logger.error("Failed to get drive information: %s", ex)
            return None
        return [
            drive for drive in json.loads(output)["blockdevices"]
            if drive["fstype"] != "squashfs"
        ]

    @staticmethod
    def get_ram_info():
        """Return RAM information"""
        try:
            output = subprocess.check_output(["free"]).decode().split("\n")
        except subprocess.CalledProcessError as ex:
            logger.error("Failed to get RAM information: %s", ex)
            return None
        columns = output[0].split()
        meminfo = {}
        for parts in [line.split() for line in output[1:] if line]:
            meminfo[parts[0].strip(":").lower()] = dict(zip(columns, parts[1:]))
        return meminfo

    @staticmethod
    def get_dist_info():
        """Return distribution information"""
        return linux_distribution()

    @staticmethod
    def get_arch():
        """Return the system architecture only if compatible
        with the supported architectures from the Lutris API
        """
        machine = platform.machine()
        if "64" in machine:
            return "x86_64"
        if "86" in machine:
            return "i386"
        if "armv7" in machine:
            return "armv7"
        logger.warning("Unsupported architecture %s", machine)

    @property
    def runtime_architectures(self):
        if self.arch == "x86_64":
            return ["i386", "x86_64"]
        return ["i386"]

    @property
    def requirements(self):
        return self.get_requirements()

    @property
    def critical_requirements(self):
        return self.get_requirements(include_optional=False)

    @property
    def lib_folders(self):
        return self.get_lib_folders()

    def get_lib_folders(self):
        _paths32 = []
        _paths64 = []
        for candidate in (subprocess.Popen(['ldconfig', '-p'], stdout=subprocess.PIPE, text=True)).communicate()[0].split('\n'):
            for req in self.requirements:
                for lib in SYSTEM_COMPONENTS["LIBRARIES"][req]:
                    if lib in candidate:
                        if 'x86-64' in candidate:
                            candidate = candidate.split(' => ')[1].split(lib)[0]
                            if candidate not in _paths64:
                                _paths64.append(candidate)
                        else:
                            candidate = candidate.split(' => ')[1].split(lib)[0]
                            if candidate not in _paths32:
                                _paths32.append(candidate)
        return (sorted(_paths32, key = len, reverse = True), sorted(_paths64, key = len, reverse = True))

    def get_glxinfo(self):
        """Return a GlxInfo instance if the gfxinfo tool is available"""
        if not self.get("glxinfo"):
            return
        _glxinfo = glxinfo.GlxInfo()
        if not hasattr(_glxinfo, "display"):
            logger.warning("Invalid glxinfo received")
            return
        return _glxinfo

    def get_requirements(self, include_optional=True):
        """Return used system requirements"""
        _requirements = self.required_components.copy()
        if include_optional:
            _requirements += self.optional_components
            if drivers.is_amd():
                _requirements.append("RADEON")
        return _requirements

    def get(self, command):
        """Return a system command path if available"""
        return self._cache["COMMANDS"].get(command)

    def get_terminals(self):
        """Return list of installed terminals"""
        return list(self._cache["TERMINALS"].values())

    def get_soundfonts(self):
        """Return path of available soundfonts"""
        return self._cache["SOUNDFONTS"]

    def iter_lib_folders(self):
        """Loop over existing 32/64 bit library folders"""
        for lib_paths in self.lib_folders:
            if self.arch != 'x86_64':
                # On non amd64 setups, only the first element is relevant
                lib_paths = [lib_paths[0]]
            #if all([os.path.exists(path) for path in lib_paths]):
            print(lib_paths)
            yield lib_paths

    def populate_libraries(self):
        """Populates the LIBRARIES cache with what is found on the system"""
        self._cache["LIBRARIES"] = {}
        for arch in self.runtime_architectures:
            self._cache["LIBRARIES"][arch] = defaultdict(list)
        for lib_paths in self.iter_lib_folders():
            for path in lib_paths:
                for req in self.requirements:
                    for lib in SYSTEM_COMPONENTS["LIBRARIES"][req]:
                        for index, arch in enumerate(self.runtime_architectures):
                            if os.path.exists(os.path.join(lib_paths[index], lib)):
                                self._cache["LIBRARIES"][arch][req].append(lib)

    def populate_sound_fonts(self):
        """Populates the soundfont cache"""
        self._cache["SOUNDFONTS"] = []
        for folder in self.soundfont_folders:
            if not os.path.exists(folder):
                continue
            for soundfont in os.listdir(folder):
                self._cache["SOUNDFONTS"].append(soundfont)

    def get_missing_requirement_libs(self, req):
        """Return a list of sets of missing libraries for each supported architecture"""
        required_libs = set(SYSTEM_COMPONENTS["LIBRARIES"][req])
        return [
            list(required_libs - set(self._cache["LIBRARIES"][arch][req]))
            for arch in self.runtime_architectures
        ]

    def get_missing_libs(self):
        """Return a dictionary of missing libraries"""
        return {
            req: self.get_missing_requirement_libs(req)
            for req in self.requirements
        }

    def is_feature_supported(self, feature):
        """Return whether the system has the necessary libs to support a feature"""
        return not self.get_missing_requirement_libs(feature)[0]


LINUX_SYSTEM = LinuxSystem()
