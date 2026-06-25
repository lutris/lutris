"""System package dependency detection for Wine/DXVK/Vulkan requirements.

Detects missing system packages needed for Wine games to run correctly,
identifies the appropriate package manager for the current distro, and
builds the exact install command needed to resolve missing dependencies.
"""

import json
import os
import shutil
import urllib.request
from typing import Optional

from lutris.util.graphics import drivers
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger

KRON4EK_RELEASES_API = "https://api.github.com/repos/Kron4ek/Wine-Builds/releases/latest"
KRON4EK_DOWNLOAD_BASE = "https://github.com/Kron4ek/Wine-Builds/releases/download"
WINE_RUNNERS_DIR = os.path.expanduser("~/.local/share/lutris/runners/wine")

# Maps distro ID (from /etc/os-release) to package manager
DISTRO_PACKAGE_MANAGERS: dict[str, str] = {
    # Debian/Ubuntu family
    "ubuntu": "apt",
    "debian": "apt",
    "pop-os": "apt",
    "pop": "apt",
    "linuxmint": "apt",
    "elementary": "apt",
    "zorin": "apt",
    "kali": "apt",
    "parrot": "apt",
    # Arch family
    "arch": "pacman",
    "manjaro": "pacman",
    "endeavouros": "pacman",
    "cachyos": "pacman",
    "garuda": "pacman",
    "artix": "pacman",
    "arcolinux": "pacman",
    # Fedora/RHEL family
    "fedora": "dnf",
    "rhel": "dnf",
    "centos": "dnf",
    "nobara": "dnf",
    "rocky": "dnf",
    "alma": "dnf",
    # openSUSE
    "opensuse-leap": "zypper",
    "opensuse-tumbleweed": "zypper",
    "suse": "zypper",
}

# Required packages per package manager per GPU vendor.
# These are the packages users most commonly lack when Wine/DXVK fails.
WINE_REQUIRED_PACKAGES: dict[str, dict[str, list[str]]] = {
    "apt": {
        "amd": [
            "libvulkan1",
            "libvulkan1:i386",
            "mesa-vulkan-drivers",
            "mesa-vulkan-drivers:i386",
            "libgl1-mesa-dri:i386",
        ],
        "nvidia": [
            "libvulkan1",
            "libvulkan1:i386",
            "nvidia-driver-libs:i386",
        ],
        "intel": [
            "libvulkan1",
            "libvulkan1:i386",
            "mesa-vulkan-drivers",
            "mesa-vulkan-drivers:i386",
        ],
    },
    "pacman": {
        "amd": [
            "vulkan-radeon",
            "lib32-vulkan-radeon",
            "vulkan-icd-loader",
            "lib32-vulkan-icd-loader",
        ],
        "nvidia": [
            "nvidia-utils",
            "lib32-nvidia-utils",
            "vulkan-icd-loader",
            "lib32-vulkan-icd-loader",
        ],
        "intel": [
            "vulkan-intel",
            "lib32-vulkan-intel",
            "vulkan-icd-loader",
            "lib32-vulkan-icd-loader",
        ],
    },
    "dnf": {
        "amd": [
            "mesa-vulkan-drivers",
            "mesa-vulkan-drivers.i686",
            "vulkan-loader",
            "vulkan-loader.i686",
        ],
        "nvidia": [
            "vulkan-loader",
            "vulkan-loader.i686",
        ],
        "intel": [
            "mesa-vulkan-drivers",
            "mesa-vulkan-drivers.i686",
            "vulkan-loader",
            "vulkan-loader.i686",
        ],
    },
    "zypper": {
        "amd": [
            "libvulkan_radeon",
            "libvulkan_radeon-32bit",
            "libvulkan1",
            "libvulkan1-32bit",
        ],
        "nvidia": [
            "libvulkan1",
            "libvulkan1-32bit",
        ],
        "intel": [
            "libvulkan_intel",
            "libvulkan_intel-32bit",
            "libvulkan1",
            "libvulkan1-32bit",
        ],
    },
}

# Base install command per package manager (packages are appended)
INSTALL_COMMANDS: dict[str, list[str]] = {
    "apt": ["apt-get", "install", "-y"],
    "pacman": ["pacman", "-S", "--noconfirm"],
    "dnf": ["dnf", "install", "-y"],
    "zypper": ["zypper", "install", "-y"],
}


def get_package_manager() -> Optional[str]:
    """Detect the system package manager from distro ID.

    Falls back to probing for known package manager binaries if the distro
    ID is not in our map, so uncommon distros still get a best-effort result.
    """
    dist_info = LINUX_SYSTEM.get_dist_info()
    if dist_info and dist_info != "unknown":
        distro_id = dist_info[0].lower().replace(" ", "-") if isinstance(dist_info, tuple) else ""
        if distro_id in DISTRO_PACKAGE_MANAGERS:
            return DISTRO_PACKAGE_MANAGERS[distro_id]

    # Fallback: probe for binaries directly
    for binary, manager in [("apt-get", "apt"), ("pacman", "pacman"), ("dnf", "dnf"), ("zypper", "zypper")]:
        if shutil.which(binary):
            logger.debug("Detected package manager '%s' via binary probe", manager)
            return manager

    logger.warning("Could not detect a supported package manager")
    return None


def get_gpu_vendor() -> str:
    """Return the active GPU vendor as a simple string: 'amd', 'nvidia', or 'intel'."""
    if drivers.is_amd():
        return "amd"
    if drivers.is_nvidia():
        return "nvidia"
    return "intel"


def get_required_packages(package_manager: str, gpu_vendor: str) -> list[str]:
    """Return the list of packages required for Wine/DXVK on this GPU and distro."""
    return WINE_REQUIRED_PACKAGES.get(package_manager, {}).get(gpu_vendor, [])


def get_missing_packages(required: list[str], package_manager: str) -> list[str]:
    """Filter required packages down to those not currently installed.

    Uses ldconfig for library-backed packages and binary probing for tools.
    For apt systems, also checks dpkg to catch installed-but-uncached packages.
    """
    if not required:
        return []

    if package_manager == "apt":
        return _get_missing_apt_packages(required)

    # For non-apt systems, fall back to checking whether the core Vulkan
    # library is visible to the dynamic linker as a proxy for full installation.
    missing_vulkan_arches = LINUX_SYSTEM.get_missing_lib_arch("VULKAN")
    if missing_vulkan_arches:
        logger.debug("Vulkan missing on architectures: %s", missing_vulkan_arches)
        return required

    return []


def _get_missing_apt_packages(packages: list[str]) -> list[str]:
    """Check which packages from the list are not installed via dpkg."""
    import subprocess

    missing = []
    for pkg in packages:
        # Strip architecture suffix for dpkg query (e.g. libvulkan1:i386 → libvulkan1:i386 is valid for dpkg)
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f=${Status}", pkg],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "install ok installed" not in result.stdout:
                missing.append(pkg)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # dpkg not available or timed out — include package as potentially missing
            missing.append(pkg)
    return missing


def get_install_command(package_manager: str, packages: list[str]) -> Optional[list[str]]:
    """Build the full install command for the given package manager and package list."""
    base = INSTALL_COMMANDS.get(package_manager)
    if not base or not packages:
        return None
    return base + packages


def check_wine_dependencies() -> Optional[dict]:
    """Top-level check: detect GPU, distro, missing packages, and return a
    result dict if action is needed, or None if everything looks good.

    Returns:
        None if no missing dependencies are found.
        dict with keys:
            'gpu_vendor'      — 'amd', 'nvidia', or 'intel'
            'package_manager' — e.g. 'apt'
            'missing'         — list of missing package names
            'install_command' — full command list ready to pass to subprocess
    """
    package_manager = get_package_manager()
    if not package_manager:
        logger.warning("Cannot check Wine dependencies: unsupported package manager")
        return None

    gpu_vendor = get_gpu_vendor()
    required = get_required_packages(package_manager, gpu_vendor)
    missing = get_missing_packages(required, package_manager)

    if not missing:
        return None

    install_command = get_install_command(package_manager, missing)
    if not install_command:
        return None

    logger.info(
        "Missing Wine dependencies for %s GPU on %s: %s",
        gpu_vendor.upper(),
        package_manager,
        ", ".join(missing),
    )

    return {
        "gpu_vendor": gpu_vendor,
        "package_manager": package_manager,
        "missing": missing,
        "install_command": install_command,
    }


def _has_staging_runner() -> bool:
    """Return True if any wine-staging runner is already installed locally."""
    if not os.path.exists(WINE_RUNNERS_DIR):
        return False
    for entry in os.listdir(WINE_RUNNERS_DIR):
        if "staging" in entry.lower():
            return True
    return False


def check_wine_staging_runner(current_version: Optional[str] = None) -> Optional[dict]:
    """Check whether a Wine Staging runner is available.

    If the game is already configured to use a staging, GE, or Proton runner,
    or if any staging runner is already installed, returns None.  Otherwise
    fetches the latest Kron4ek wine-staging release and returns install info.

    Returns:
        None if no action is needed.
        dict with keys:
            'version'     — runner directory name, e.g. 'wine-11.11-staging-amd64'
            'url'         — tarball download URL
            'runner_dir'  — destination parent directory for extraction
    """
    if current_version:
        cv = current_version.lower()
        if any(kw in cv for kw in ("staging", "ge", "proton", "tkg")):
            return None

    if _has_staging_runner():
        return None

    try:
        req = urllib.request.Request(KRON4EK_RELEASES_API, headers={"User-Agent": "lutris-game-manager"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        tag = data["tag_name"]
        filename = f"wine-{tag}-staging-amd64.tar.xz"
        url = f"{KRON4EK_DOWNLOAD_BASE}/{tag}/{filename}"
        return {
            "version": f"wine-{tag}-staging-amd64",
            "url": url,
            "runner_dir": WINE_RUNNERS_DIR,
        }
    except Exception as ex:  # pylint: disable=broad-except
        logger.warning("Could not fetch Wine Staging release info: %s", ex)
        return None
