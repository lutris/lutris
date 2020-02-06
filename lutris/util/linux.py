"""Linux specific platform code"""
import os
import re
import shutil
import sys
import json
import platform
import resource
import subprocess
from collections import defaultdict, Counter

from lutris.util.log import logger

try:
    from distro import linux_distribution
except ImportError:
    logger.warning("Package 'distro' unavailable. Unable to read Linux distribution")
    linux_distribution = None
from lutris.util.graphics import drivers
from lutris.util.graphics import glxinfo
from lutris.util.graphics import vkquery
from lutris.util.disks import get_drive_for_path

# Linux components used by lutris
SYSTEM_COMPONENTS = {
    "COMMANDS": [
        "xrandr",
        "fuser",
        "glxinfo",
        "vulkaninfo",
        "optirun",
        "primusrun",
        "pvkrun",
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
        "alacritty",
    ],
    "LIBRARIES": {
        "OPENGL": ["libGL.so.1"],
        "VULKAN": ["libvulkan.so.1"],
        "WINE": ["libsqlite3.so.0"],
        "RADEON": ["libvulkan_radeon.so"],
        "GAMEMODE": ["libgamemodeauto.so"],
    },
}


class LinuxSystem:
    """Global cache for system commands"""

    _cache = {}

    multiarch_lib_folders = [
        ("/lib", "/lib64"),
        ("/lib32", "/lib64"),
        ("/usr/lib", "/usr/lib64"),
        ("/usr/lib32", "/usr/lib64"),
        ("/lib/i386-linux-gnu", "/lib/x86_64-linux-gnu"),
        ("/usr/lib/i386-linux-gnu", "/usr/lib/x86_64-linux-gnu"),
    ]

    soundfont_folders = [
        "/usr/share/sounds/sf2",
        "/usr/share/soundfonts",
    ]

    recommended_no_file_open = 524288
    required_components = ["OPENGL", "VULKAN"]
    optional_components = ["WINE", "GAMEMODE"]

    flatpak_info_path = "/.flatpak-info"

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
        self.shared_libraries = self.get_shared_libraries()
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
            drive
            for drive in json.loads(output)["blockdevices"]
            if drive["fstype"] != "squashfs"
        ]

    @staticmethod
    def get_ram_info():
        """Parse the output of /proc/meminfo and return RAM information in kB"""
        mem = {}
        with open("/proc/meminfo") as meminfo:
            for line in meminfo.readlines():
                key, value = line.split(":", 1)
                mem[key.strip()] = value.strip('kB \n')
        return mem

    @staticmethod
    def get_dist_info():
        """Return distribution information"""
        if linux_distribution:
            return linux_distribution()
        return "unknown"

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

    @staticmethod
    def get_kernel_version():
        """Get kernel info from /proc/version"""
        with open("/proc/version") as kernel_info:
            info = kernel_info.readlines()[0]
            version = info.split(" ")[2]
        return version

    @property
    def is_flatpak(self):
        """Check is we are running inside Flatpak sandbox"""
        return os.path.exists(self.flatpak_info_path)

    @property
    def runtime_architectures(self):
        """Return the architectures supported on this machine"""
        if self.arch == "x86_64":
            return ["i386", "x86_64"]
        return ["i386"]

    @property
    def requirements(self):
        return self.get_requirements()

    @property
    def critical_requirements(self):
        return self.get_requirements(include_optional=False)

    def get_fs_type_for_path(self, path):
        """Return the filesystem type a given path uses"""
        path_drive = get_drive_for_path(path)
        for drive in self.get_drives():
            for partition in drive.get("children", []):
                if "/dev/%s" % partition["name"] == path_drive:
                    return partition["fstype"]

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

    def get_lib_folders(self):
        """Return shared library folders, sorted by most used to least used"""
        lib_folder_counter = Counter(
            lib.dirname
            for lib_list in self.shared_libraries.values()
            for lib in lib_list
        )
        return [path[0] for path in reversed(lib_folder_counter.most_common())]

    def iter_lib_folders(self):
        """Loop over existing 32/64 bit library folders"""
        exported_lib_folders = set()
        for lib_folder in self.get_lib_folders():
            exported_lib_folders.add(lib_folder)
            yield lib_folder
        for lib_paths in self.multiarch_lib_folders:
            if self.arch != "x86_64":
                # On non amd64 setups, only the first element is relevant
                lib_paths = [lib_paths[0]]
            else:
                # Ignore paths where 64-bit path is link to supposed 32-bit path
                if os.path.realpath(lib_paths[0]) == os.path.realpath(lib_paths[1]):
                    continue
            if all([os.path.exists(path) for path in lib_paths]):
                if lib_paths[0] not in exported_lib_folders:
                    yield lib_paths[0]
                if len(lib_paths) != 1:
                    if lib_paths[1] not in exported_lib_folders:
                        yield lib_paths[1]

    def get_ldconfig_libs(self):
        """Return a list of available libraries, as returned by `ldconfig -p`."""
        ldconfig = self.get("ldconfig")
        if not ldconfig:
            logger.error("Could not detect ldconfig on this system")
            return []
        try:
            output = (
                subprocess.check_output([ldconfig, "-p"])
                .decode("utf-8", errors="ignore")
                .split("\n")
            )
        except subprocess.CalledProcessError as ex:
            logger.error("Failed to get libraries from ldconfig: %s", ex)
            return []
        return [line.strip("\t") for line in output if line.startswith("\t")]

    def get_shared_libraries(self):
        """Loads all available libraries on the system as SharedLibrary instances
        The libraries are stored in a defaultdict keyed by library name.
        """
        shared_libraries = defaultdict(list)
        for lib_line in self.get_ldconfig_libs():
            lib = SharedLibrary.new_from_ldconfig(lib_line)
            if lib.arch not in self.runtime_architectures:
                continue
            shared_libraries[lib.name].append(lib)
        return shared_libraries

    def populate_libraries(self):
        """Populates the LIBRARIES cache with what is found on the system"""
        self._cache["LIBRARIES"] = {}
        for arch in self.runtime_architectures:
            self._cache["LIBRARIES"][arch] = defaultdict(list)
        for req in self.requirements:
            for lib in SYSTEM_COMPONENTS["LIBRARIES"][req]:
                for shared_lib in self.shared_libraries[lib]:
                    self._cache["LIBRARIES"][shared_lib.arch][req].append(lib)

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
            req: self.get_missing_requirement_libs(req) for req in self.requirements
        }

    def is_feature_supported(self, feature):
        """Return whether the system has the necessary libs to support a feature"""
        return not self.get_missing_requirement_libs(feature)[0]


class SharedLibrary:
    """Representation of a Linux shared library"""

    default_arch = "i386"

    def __init__(self, name, flags, path):
        self.name = name
        self.flags = [flag.strip() for flag in flags.split(",")]
        self.path = path

    @classmethod
    def new_from_ldconfig(cls, ldconfig_line):
        """Create a SharedLibrary instance from an output line from ldconfig"""
        lib_match = re.match(r"^(.*) \((.*)\) => (.*)$", ldconfig_line)
        if not lib_match:
            raise ValueError(
                "Received incorrect value for ldconfig line: %s" % ldconfig_line
            )
        return cls(lib_match.group(1), lib_match.group(2), lib_match.group(3))

    @property
    def arch(self):
        """Return the architecture for a shared library"""
        detected_arch = ["x86-64", "x32"]
        for arch in detected_arch:
            if arch in self.flags:
                return arch.replace("-", "_")
        return self.default_arch

    @property
    def basename(self):
        """Return the name of the library without an extention"""
        return self.name.split(".so")[0]

    @property
    def dirname(self):
        """Return the directory where the lib resides"""
        return os.path.dirname(self.path)

    def __str__(self):
        return "%s (%s)" % (self.name, self.arch)


LINUX_SYSTEM = LinuxSystem()


def gather_system_info():
    """Get all system information in a single data structure"""
    system_info = {}
    if drivers.is_nvidia():
        system_info["nvidia_driver"] = drivers.get_nvidia_driver_info()
        system_info["nvidia_gpus"] = [
            drivers.get_nvidia_gpu_info(gpu_id)
            for gpu_id in drivers.get_nvidia_gpu_ids()
        ]
    system_info["gpus"] = [drivers.get_gpu_info(gpu) for gpu in drivers.get_gpus()]
    system_info["env"] = dict(os.environ)
    system_info["missing_libs"] = LINUX_SYSTEM.get_missing_libs()
    system_info["cpus"] = LINUX_SYSTEM.get_cpus()
    system_info["drives"] = LINUX_SYSTEM.get_drives()
    system_info["ram"] = LINUX_SYSTEM.get_ram_info()
    system_info["dist"] = LINUX_SYSTEM.get_dist_info()
    system_info["arch"] = LINUX_SYSTEM.get_arch()
    system_info["kernel"] = LINUX_SYSTEM.get_kernel_version()
    system_info["glxinfo"] = glxinfo.GlxInfo().as_dict()
    return system_info


def gather_system_info_str():
    """Get all relevant system information already formatted as a string"""
    system_info = gather_system_info()
    system_info_readable = {}
    # Add system information
    system_dict = {}
    system_dict["OS"] = ' '.join(system_info["dist"])
    system_dict["Arch"] = system_info["arch"]
    system_dict["Kernel"] = system_info["kernel"]
    system_dict["Desktop"] = system_info["env"].get("XDG_CURRENT_DESKTOP", "Not found")
    system_dict["Display Server"] = system_info["env"].get("XDG_SESSION_TYPE", "Not found")
    system_info_readable["System"] = system_dict
    # Add CPU information
    cpu_dict = {}
    cpu_dict["Vendor"] = system_info["cpus"][0]["vendor_id"]
    cpu_dict["Model"] = system_info["cpus"][0]["model name"]
    cpu_dict["Physical cores"] = system_info["cpus"][0]["cpu cores"]
    cpu_dict["Logical cores"] = system_info["cpus"][0]["siblings"]
    system_info_readable["CPU"] = cpu_dict
    # Add memory information
    ram_dict = {}
    ram_dict["RAM"] = "%0.1f GB" % (float(system_info["ram"]["MemTotal"]) / 1024 / 1024)
    ram_dict["Swap"] = "%0.1f GB" % (float(system_info["ram"]["SwapTotal"]) / 1024 / 1024)
    system_info_readable["Memory"] = ram_dict
    # Add graphics information
    graphics_dict = {}
    if LINUX_SYSTEM.glxinfo:
        graphics_dict["Vendor"] = system_info["glxinfo"]["opengl_vendor"]
        graphics_dict["OpenGL Renderer"] = system_info["glxinfo"]["opengl_renderer"]
        graphics_dict["OpenGL Version"] = system_info["glxinfo"]["opengl_version"]
        graphics_dict["OpenGL Core"] = system_info["glxinfo"]["opengl_core_profile_version"]
        graphics_dict["OpenGL ES"] = system_info["glxinfo"]["opengl_es_profile_version"]
    else:
        graphics_dict["Vendor"] = "Unable to obtain glxinfo"
    # check Vulkan support
    if vkquery.is_vulkan_supported():
        graphics_dict["Vulkan"] = "Supported"
    else:
        graphics_dict["Vulkan"] = "Not Supported"
    system_info_readable["Graphics"] = graphics_dict

    output = ''
    for section in system_info_readable:
        output += '[{}]\n'.format(section)
        dictionary = system_info_readable[section]
        for key in dictionary:
            tabs = " " * (16 - len(key))
            output += '{}{}{}\n'.format(key + ":", tabs, dictionary[key])
        output += '\n'
    return output
