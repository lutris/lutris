"""Automatically detects game executables in a folder"""

import os
import re
from collections import defaultdict

from lutris.util import magic, system
from lutris.util.log import logger


def normalize_name(name):
    """Reduces a name to just its letters and digits, so an executable can be
    compared against the name of the folder holding it."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def sort_candidates(candidates, game_name):
    """Orders equally valid executables so the same one is always picked. Those named
    after the game folder come first; ties are then broken by preferring the longest
    name, on the grounds that a longer one is the more specific of the two, and finally
    by alphabetical order so the result never depends on the order files are listed in.

    Length is measured on the name as written, punctuation and spaces included, but
    without the extension so that a longer suffix can't outweigh the name itself."""

    def sort_key(path):
        basename = os.path.basename(path)
        name = os.path.splitext(basename)[0]
        stem = normalize_name(name)
        if game_name and stem:
            if stem == game_name:
                rank = 0
            elif stem.startswith(game_name) or game_name.startswith(stem):
                rank = 1
            else:
                rank = 2
        else:
            rank = 2
        return rank, -len(name), basename.lower()

    return sorted(candidates, key=sort_key)


def is_excluded_elf(filename):
    excluded = (
        "xdg-open",
        "uninstall",
        # Unity ships its engine and crash reporter alongside the game binary
        "unitycrashhandler",
        "unityplayer",
    )
    _fn = filename.lower()
    if _fn.endswith(".debug"):  # detached debug symbols, not a program
        return True
    if re.search(r"\.so(\.\d+)*$", _fn):  # a shared library, versioned or not
        return True
    return any(exclude in _fn for exclude in excluded)


def find_linux_game_executable(path, make_executable=False):
    """Looks for a binary or shell script that launches the game in a directory"""
    game_name = normalize_name(os.path.basename(os.path.normpath(path)))

    for base, _dirs, files in os.walk(path):
        candidates = defaultdict(list)
        for _file in files:
            if is_excluded_elf(_file):
                continue
            abspath = os.path.join(base, _file)
            file_type = magic.from_file(abspath)
            if "ASCII text executable" in file_type:
                candidates["shell"].append(abspath)
            if "Bourne-Again shell script" in file_type:
                candidates["bash"].append(abspath)
            if "POSIX shell script executable" in file_type:
                candidates["posix"].append(abspath)
            if "64-bit LSB executable" in file_type or "64-bit LSB pie executable" in file_type:
                candidates["64bit"].append(abspath)
            if "32-bit LSB executable" in file_type or "32-bit LSB pie executable" in file_type:
                candidates["32bit"].append(abspath)
            # A shared object is a library, but libmagic older than 5.33 has no separate
            # wording for PIE executables and reports those as shared objects too, so
            # they are kept as a last resort rather than discarded.
            if "64-bit LSB shared object" in file_type:
                candidates["64bit-so"].append(abspath)
            if "32-bit LSB shared object" in file_type:
                candidates["32bit-so"].append(abspath)
        if candidates:
            if make_executable:
                for candidate_list in candidates.values():
                    for candidate in candidate_list:
                        system.make_executable(candidate)
            best = (
                candidates.get("shell")
                or candidates.get("bash")
                or candidates.get("posix")
                or candidates.get("64bit")
                or candidates.get("32bit")
                or candidates.get("64bit-so")
                or candidates.get("32bit-so")
            )
            return sort_candidates(best, game_name)[0]
    logger.error("Couldn't find a Linux executable in %s", path)
    return ""


def is_excluded_dir(path):
    excluded = (
        "Internet Explorer",
        "Windows NT",
        "Common Files",
        "Windows Media Player",
        "windows",
        "ProgramData",
        "users",
        "GameSpy Arcade",
    )
    return any(dir_name in excluded for dir_name in path.split("/"))


def is_excluded_exe(filename):
    excluded = (
        "unins000",
        "uninstal",
        "update",
        "setup",
        "config.exe",
        "gsarcade.exe",
        "dosbox.exe",
        # Unity ships a crash reporter alongside the game's own executable
        "unitycrashhandler",
    )
    _fn = filename.lower()
    return any(exclude in _fn for exclude in excluded)


def find_windows_game_executable(path):
    game_name = normalize_name(os.path.basename(os.path.normpath(path)))

    for base, _dirs, files in os.walk(path):
        candidates = defaultdict(list)
        if is_excluded_dir(base):
            continue
        for _file in files:
            if is_excluded_exe(_file):
                continue
            abspath = os.path.join(base, _file)
            if os.path.islink(abspath):
                continue
            file_type = magic.from_file(abspath)
            if "MS Windows shortcut" in file_type:
                candidates["link"].append(abspath)
            elif "(DLL)" in file_type:
                # Libraries like UnityPlayer.dll are reported as GUI PE files too,
                # but they can't be launched.
                continue
            elif all([_ in file_type for _ in ("PE32+ executable", "(GUI)", "x86-64")]):
                candidates["64bit"].append(abspath)
            elif all([_ in file_type for _ in ("PE32 executable", "(GUI)")]) and any(
                [_ in file_type for _ in ("Intel i386", "Intel 80386")]
            ):
                candidates["32bit"].append(abspath)
        if candidates:
            best = candidates.get("link") or candidates.get("64bit") or candidates.get("32bit")
            return sort_candidates(best, game_name)[0]
    logger.error("Couldn't find a Windows executable in %s", path)
    return ""
