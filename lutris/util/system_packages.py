"""System package dependency detection for Wine/DXVK/Vulkan requirements.

Detects missing system packages needed for Wine games to run correctly,
identifies the appropriate package manager for the current distro, and
builds the exact install command needed to resolve missing dependencies.
"""

import shutil
from typing import Optional

from lutris.util.graphics import drivers
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger

# Runtime libraries that Wine prebuilt runners expect to find on the host system.
# These are NOT Wine's own package dependencies — Lutris downloads Wine as a binary
# and bypasses the package manager, so these system libs never get auto-installed.
# We check for the most common sources of silent Wine launch failures: Vulkan/DXVK
# drivers and GnuTLS (required for any HTTPS connection from within Wine).
WINE_REQUIRED_PACKAGES: dict[str, dict[str, list[str]]] = {
    "apt": {
        "amd": [
            "libvulkan1",
            "libvulkan1:i386",
            "mesa-vulkan-drivers",
            "mesa-vulkan-drivers:i386",
            "libgl1-mesa-dri:i386",
            "libgnutls30:i386",
        ],
        "nvidia": [
            "libvulkan1",
            "libvulkan1:i386",
            "nvidia-driver-libs:i386",
            "libgnutls30:i386",
        ],
        "intel": [
            "libvulkan1",
            "libvulkan1:i386",
            "mesa-vulkan-drivers",
            "mesa-vulkan-drivers:i386",
            "libgnutls30:i386",
        ],
    },
    "pacman": {
        "amd": [
            "vulkan-radeon",
            "lib32-vulkan-radeon",
            "vulkan-icd-loader",
            "lib32-vulkan-icd-loader",
            "lib32-gnutls",
        ],
        "nvidia": [
            "nvidia-utils",
            "lib32-nvidia-utils",
            "vulkan-icd-loader",
            "lib32-vulkan-icd-loader",
            "lib32-gnutls",
        ],
        "intel": [
            "vulkan-intel",
            "lib32-vulkan-intel",
            "vulkan-icd-loader",
            "lib32-vulkan-icd-loader",
            "lib32-gnutls",
        ],
    },
    "dnf": {
        "amd": [
            "mesa-vulkan-drivers",
            "mesa-vulkan-drivers.i686",
            "vulkan-loader",
            "vulkan-loader.i686",
            "gnutls.i686",
        ],
        "nvidia": [
            "vulkan-loader",
            "vulkan-loader.i686",
            "gnutls.i686",
        ],
        "intel": [
            "mesa-vulkan-drivers",
            "mesa-vulkan-drivers.i686",
            "vulkan-loader",
            "vulkan-loader.i686",
            "gnutls.i686",
        ],
    },
    "zypper": {
        "amd": [
            "libvulkan_radeon",
            "libvulkan_radeon-32bit",
            "libvulkan1",
            "libvulkan1-32bit",
            "libgnutls30-32bit",
        ],
        "nvidia": [
            "libvulkan1",
            "libvulkan1-32bit",
            "libgnutls30-32bit",
        ],
        "intel": [
            "libvulkan_intel",
            "libvulkan_intel-32bit",
            "libvulkan1",
            "libvulkan1-32bit",
            "libgnutls30-32bit",
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
    """Detect the system package manager by probing for known binaries."""
    for binary, manager in [("apt-get", "apt"), ("pacman", "pacman"), ("dnf", "dnf"), ("zypper", "zypper")]:
        if shutil.which(binary):
            logger.debug("Detected package manager '%s'", manager)
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
