import os
import shutil
import sys
from copy import copy
from typing import List

PROGRAM_FILES_IGNORES = {
    "Common Files": {"Microsoft Shared": "*", "System": "*", "InstallShield": "*"},
    "Internet Explorer": "*",
    "Windows Media Player": "*",
    "Windows NT": "*",
    "InstallShield Installation Information": "*",
    "Microsoft XNA": "*",
    "Microsoft.NET": "*",
    "GameSpy Arcade": "*",
}

IGNORED_DIRS = {
    "ProgramData": {
        "Microsoft": {"Windows": "*"},
        "GOG.com": "*",
        "Package Cache": "*",
    },
    "Program Files": PROGRAM_FILES_IGNORES,
    "Program Files (x86)": PROGRAM_FILES_IGNORES,
    "windows": "*",
    "users": {
        "Public": "*",
        os.getenv("USER"): {
            "Desktop": "*",
            "Videos": "*",
            "Temp": "*",
            "Cookies": "*",
            "AppData": {
                "LocalLow": "*",
                "Local": {"Microsoft": "*"},
                "Roaming": {"Microsoft": "*", "wine_gecko": "*"},
            },
            "Local Settings": {
                "Application Data": {"Microsoft": "*"},
                "History": "*",
                "Temporary Internet Files": "*",
            },
            "Application Data": {"Microsoft": "*", "wine_gecko": "*"},
            "Start Menu": "*",
            "PrintHood": "*",
            "Favorites": "*",
            "Recent": "*",
            "Downloads": "*",
            "Templates": "*",
            "NetHood": "*",
            "My Pictures": "*",
        },
    },
}

IGNORED_EXES = [
    "UNWISE.EXE",
    "unins000.exe",
    "Uninstall.exe",
    "UnSetup.exe",
    "UE3Redist.exe",
    "dotNetFx40_Full_setup.exe",
    "sysinfo.exe",
    "register.exe",
    "UNINSTAL.EXE",
    "GSArcade.exe",
]

KNOWN_DIRS = [
    "ProgramData/Microsoft/Windows",
    "Program Files/Common Files/Microsoft Shared",
    "Program Files/Common Files/System",
    "Program Files (x86)/Common Files/System",
    "Program Files/Internet Explorer",
    "Program Files (x86)/Internet Explorer",
    "Program Files/Windows Media Player",
    "Program Files (x86)/Windows Media Player",
    "Program Files/Windows NT",
    "Program Files (x86)/Windows NT",
    "windows",
]


def delete_known_dirs(prefix_path: str) -> None:
    for known_dir in KNOWN_DIRS:
        full_path = os.path.join(prefix_path, "drive_c", known_dir)
        if not os.path.exists(full_path):
            continue
        print("Deleting %s", full_path)
        shutil.rmtree(full_path)


def remove_empty_dirs(dirname: str) -> List[str]:
    empty_folders = []
    for root, dirs, files in os.walk(dirname, topdown=True):
        if not files and not dirs:
            empty_folders.append(root)
    for folder in empty_folders:
        os.rmdir(folder)
    return empty_folders


def cleanup_prefix(path: str) -> None:
    print("Cleanup prefix", path)
    delete_known_dirs(path)
    empty_folders = True
    while empty_folders:
        empty_folders = remove_empty_dirs(path)


def is_ignored_path(path_parts: List[str]) -> bool:
    ignored_dirs = copy(IGNORED_DIRS)
    if len(path_parts) in (0, 1):
        return True
    for level, part in enumerate(path_parts):
        if level == 0:
            if part == "dosdevices":
                return True
        if part in ignored_dirs:
            if ignored_dirs[part] == "*":
                return True
            ignored_dirs = ignored_dirs[part]
    return False


def get_content_folders(path: str) -> List[str]:
    found_dirs = []
    for root, _dirs, files in os.walk(path, topdown=True):
        # print(root, files, dirs)
        relpath = root[len(path) :].strip("/")
        path_parts = relpath.split("/")
        if is_ignored_path(path_parts):
            continue
        if files:
            found_dirs.append(root)
    folders = []
    for found_dir in found_dirs:
        skip = False
        for _dir in folders:
            if found_dir.startswith(_dir):
                skip = True
        if skip:
            continue
        folders.append(found_dir)
    return folders


def find_exes_in_path(folder: str) -> List[str]:
    exes = []
    for filename in os.listdir(folder):
        abspath = os.path.join(folder, filename)
        if os.path.isdir(abspath):
            exes += find_exes_in_path(abspath)
        if os.path.isfile(abspath):
            if filename in IGNORED_EXES:
                continue
            if filename.lower().endswith(".exe"):
                exes.append(os.path.join(folder, filename))
    return exes


def scan_prefix(path: str) -> None:
    print("Scanning prefix %s", path)
    folders = get_content_folders(path)
    exes = []
    for folder in folders:
        if "drive_c/users" in folder:
            continue
        exes += find_exes_in_path(folder)
    for exe in exes:
        print("EXE", exe)


if __name__ == "__main__":
    path = sys.argv[1]
    scan_prefix(path)
    cleanup_prefix(path)
