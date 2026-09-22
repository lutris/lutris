import functools
import glob
import os
import re
import subprocess
import threading
from typing import TypeAlias

from lutris.util import system
from lutris.util.graphics import drivers
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger

VULKANINFO_PATH = system.find_executable("vulkaninfo")
VULKAN_DATA_DIRS = [
    "/usr/local/etc",  # standard site-local location
    "/usr/local/share",  # standard site-local location
    "/etc",  # standard location
    "/usr/share",  # standard location
    "/usr/lib/x86_64-linux-gnu/GL",  # Flatpak GL extension
    "/usr/lib/i386-linux-gnu/GL",  # Flatpak GL32 extension
    "/opt/amdgpu-pro/etc",  # AMD GPU Pro - TkG
]

_gpus: dict[str, "GPU"] | None = None
_gpus_lock = threading.Lock()


def get_gpus() -> dict[str, "GPU"]:
    """Return a dict of GPU objects, keyed by card name. Populated on first call."""
    global _gpus
    with _gpus_lock:
        if _gpus is None:
            gpus = {}
            for card in drivers.get_gpu_cards():
                gpu = GPU(card)
                driver_info = gpu.get_driver_info()
                logger.info('"%s" is %s Driver %s', card, gpu, driver_info.get("version"))
                gpus[card] = gpu
            _gpus = gpus
    return _gpus


def preload_gpus(async_ops: bool = True) -> None:
    """Kick off GPU detection in a background thread so it's
    likely ready by the time the user opens system configuration.
    When async_ops is False, runs synchronously on the calling thread."""
    if async_ops:
        threading.Thread(target=get_gpus, daemon=True).start()
    else:
        get_gpus()


GpuInfoDict: TypeAlias = dict[str, str]


def get_gpus_info() -> dict[str, drivers.DriverGpuInfoDict]:
    """Return the information related to each GPU on the system"""
    return {card: drivers.get_gpu_info(card) for card in drivers.get_gpu_cards()}


def display_gpu_info(gpu_id: str, gpu_info: drivers.DriverGpuInfoDict) -> None:
    """Log GPU information"""
    try:
        gpu_string = f"GPU: {gpu_info['PCI_ID']} {gpu_info['PCI_SUBSYS_ID']} ({gpu_info['DRIVER']} drivers)"
        logger.info(gpu_string)
    except KeyError:
        logger.error("Unable to get GPU information from '%s'", gpu_id)


def add_icd_search_path(paths: str) -> list[str]:
    icd_paths = []
    if paths:
        # unixy env vars with multiple paths are : delimited
        for path in paths.split(":"):
            path = os.path.join(path, "vulkan")
            if os.path.exists(path) and path not in icd_paths:
                icd_paths.append(path)
    return icd_paths


def log_vulkan_loader_messages(messages: str) -> None:
    """Selectively log the messages the Vulkan loader writes to stderr while we run
    vulkaninfo. Genuine errors are surfaced; the loader's warnings about ICDs that
    can't initialize on this host (such as Mesa's dzn/Direct3D12 driver, which has
    no D3D12 backend outside of WSL) are dropped entirely, as they're noise on
    most systems and would otherwise clutter the output even in debug mode."""
    for line in messages.splitlines():
        line = line.strip()
        if "ERROR" in line:
            logger.error("vulkaninfo: %s", line)


def get_vk_icd_files() -> list[str]:
    """Returns available vulkan ICD files in the same search order as vulkan-loader,
    but in a single list"""
    icd_search_paths = []
    for path in VULKAN_DATA_DIRS:
        icd_search_paths += add_icd_search_path(path)
    all_icd_files = []
    for data_dir in icd_search_paths:
        path = os.path.join(data_dir, "icd.d", "*.json")
        # sort here as directory enumeration order is not guaranteed in linux
        # so it's consistent every time
        icd_files = sorted(glob.glob(path))
        if icd_files:
            all_icd_files += icd_files
    return all_icd_files


@functools.cache
def read_vulkaninfo_summary(icd_files: str = "") -> str | None:
    """Return the output of 'vulkaninfo --summary', restricted to 'icd_files' if given, or None
    if it failed. vulkaninfo can take seconds to run on some drivers, so it runs once per set of
    ICD files, not once per GPU."""
    if not VULKANINFO_PATH:
        return None
    env = dict(os.environ)
    if icd_files:
        env["VK_DRIVER_FILES"] = icd_files  # Currently supported
        env["VK_ICD_FILENAMES"] = icd_files  # Deprecated
    try:
        return system.read_process_output(
            [VULKANINFO_PATH, "--summary"],
            env=env,
            error_result=None,
            stderr_handler=log_vulkan_loader_messages,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # read_process_output() already logged this; callers fall back to lspci.
        return None


class GPU:
    def __init__(self, card: str):
        self.card = card
        self.gpu_info = self.get_gpu_info()
        self.driver = self.gpu_info["DRIVER"]
        self.pci_id = self.gpu_info["PCI_ID"].lower()
        self.pci_subsys_id = self.gpu_info["PCI_SUBSYS_ID"].lower()
        self.pci_slot = self.gpu_info["PCI_SLOT_NAME"]
        self.icd_files = self.get_icd_files()
        self.device_uuid: str | None = None
        if VULKANINFO_PATH:
            vulkaninfo = self.get_vulkaninfo()
            self.device_uuid = self.get_vulkaninfo_device_uuid(vulkaninfo)
            self.name = self.get_vulkaninfo_name(vulkaninfo) or self.get_lspci_name()
        else:
            self.name = self.get_lspci_name()

    def __str__(self) -> str:
        if self.pci_id:
            return f"{self.short_name} ({self.pci_id} {self.pci_subsys_id} {self.driver})"

        return f"{self.short_name} ({self.driver})"

    def get_driver_info(self) -> drivers.DriverInfoDict:
        driver_info = {}
        if self.driver == "nvidia":
            driver_info = drivers.get_nvidia_driver_info()
        elif LINUX_SYSTEM.glxinfo:
            if hasattr(LINUX_SYSTEM.glxinfo, "GLX_MESA_query_renderer"):
                driver_info = {
                    "vendor": LINUX_SYSTEM.glxinfo.opengl_vendor,  # type: ignore
                    "version": LINUX_SYSTEM.glxinfo.GLX_MESA_query_renderer.version,
                    "device": LINUX_SYSTEM.glxinfo.GLX_MESA_query_renderer.device,
                }
        return driver_info

    def get_gpu_info(self) -> GpuInfoDict:
        """Return information about a GPU"""
        infos = {"DRIVER": "", "PCI_ID": "", "PCI_SUBSYS_ID": "", "PCI_SLOT_NAME": ""}
        try:
            with open(f"/sys/class/drm/{self.card}/device/uevent", encoding="utf-8") as card_uevent:
                content = card_uevent.readlines()
        except FileNotFoundError:
            logger.error("Unable to read driver information for card %s", self.card)
            raise
        for line in content:
            key, value = line.split("=", 1)
            infos[key] = value.strip()
        return infos

    def get_vulkaninfo(self) -> dict[str, dict[str, str]]:
        """Runs vulkaninfo to find the GPU name; returns an empty dict if vulkaninfo fails."""
        vulkaninfo_output_raw = read_vulkaninfo_summary()
        if vulkaninfo_output_raw == "" and self.icd_files:
            vulkaninfo_output_raw = read_vulkaninfo_summary(self.icd_files)

        vulkaninfo_output = vulkaninfo_output_raw.split("\n") if vulkaninfo_output_raw else []
        result = {}
        devices_seen = False
        for line in vulkaninfo_output:
            line = line.strip()
            if not line or line.startswith("==="):
                continue
            if line == "Devices:":
                devices_seen = True
                continue
            if not devices_seen:
                continue
            if line.startswith("GPU"):
                current_gpu = line
                result[current_gpu] = {}
            elif "= " in line:
                key, value = line.split("= ", maxsplit=1)
                result[current_gpu][key.strip()] = value.strip()
        if "Failed to detect any valid GPUs" in result or "ERROR: [Loader Message]" in result:
            logger.warning("Vulkan failed to detect any GPUs: %s", result)
            return {}
        return result

    def get_vulkaninfo_name(self, vulkaninfo: dict[str, dict[str, str]]) -> str | None:
        best_name = None
        for gpu_index in vulkaninfo:
            pci_id = "%s:%s" % (
                vulkaninfo[gpu_index]["vendorID"].replace("0x", ""),
                vulkaninfo[gpu_index]["deviceID"].replace("0x", ""),
            )
            if pci_id == self.pci_id:
                name = vulkaninfo[gpu_index]["deviceName"]
                if not best_name or len(name) > len(best_name):
                    best_name = name
        return best_name

    def get_vulkaninfo_device_uuid(self, vulkaninfo: dict[str, dict[str, str]]) -> str | None:
        for gpu_index in vulkaninfo:
            pci_id = "%s:%s" % (
                vulkaninfo[gpu_index]["vendorID"].replace("0x", ""),
                vulkaninfo[gpu_index]["deviceID"].replace("0x", ""),
            )
            if pci_id == self.pci_id:
                deviceUUID = vulkaninfo[gpu_index].get("deviceUUID", "").replace("-", "")
                if deviceUUID:
                    return deviceUUID
        return None

    def get_lspci_name(self) -> str:
        lspci_results = [line.split(maxsplit=1) for line in system.execute(["lspci"], timeout=3).split("\n")]
        lspci_results = [parts for parts in lspci_results if len(parts) == 2 and ": " in parts[1]]
        devices = [(pci_id, device_desc.split(": ")[1]) for pci_id, device_desc in lspci_results]
        for device in devices:
            if f"0000:{device[0]}" == self.pci_slot:
                return device[1]
        return "No GPU"

    def get_icd_files(self) -> str:
        loader = self.driver
        loader_map = {
            "amdgpu": "radeon",
            "vc4-drm": "broadcom",
            "v3d": "broadcom",
            "virtio-pci": "lvp",
            "i915": "intel",
            "xe": "intel",
        }
        if self.driver in loader_map:
            loader = loader_map[self.driver]
        icd_files = []
        for icd_file in get_vk_icd_files():
            if loader in icd_file:
                icd_files.append(icd_file)
        return ":".join(icd_files)

    @property
    def short_name(self) -> str:
        """Shorten result to just the friendly name of the GPU
        vulkaninfo returns Vendor Friendly Name (Chip Developer Name)
        AMD Radeon Pro W6800 (RADV NAVI21) -> AMD Radeon Pro W6800"""
        return re.sub(r"\s*\(.*?\)", "", self.name)
