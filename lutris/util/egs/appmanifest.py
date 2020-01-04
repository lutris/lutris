"""EGS appmanifest file handling"""
import re
import glob
import os
import json
from lutris.util.strings import slugify
from lutris.util.log import logger
from lutris.util.system import fix_path_case, path_exists
from lutris.runners.wine import wine

class AppManifest:
    def __init__(self, appmanifest_path):
        self.appmanifest_path = appmanifest_path
        self.appmanifest_data = {}

        if path_exists(appmanifest_path):
            with open(appmanifest_path, "r") as appmanifest_file:
                self.appmanifest_data = json.load(appmanifest_file)
        else:
            logger.error(
                "Path to AppManifest file %s doesn't exist", appmanifest_path)

    def __repr__(self):
        return "<AppManifest: %s>" % self.appmanifest_path

    @property
    def appid(self):
        return self.appmanifest_data.get("AppName")

    @property
    def name(self):
        return self.appmanifest_data.get("DisplayName")

    @property
    def slug(self):
        return slugify(self.name)

    @property
    def installdir(self):
        """Returns the Windows install location inside the Wine prefix"""
        return self.appmanifest_data.get("InstallLocation")

    @property
    def executable(self):
        return self.appmanifest_data.get("LaunchExecutable")

    def is_installed(self):
        # true if not completed!
        return not self.appmanifest_data.get("bIsIncompleteInstall")



def get_appmanifest_from_appid(egs_data_path, appid):
    """Given the steam apps path and appid, return the corresponding appmanifest"""
    manifests = [AppManifest(path) for path in get_appmanifests(egs_data_path)]
    return next((m for m in manifests if m.appid == appid), None)


def get_path_from_appmanifest(prefix_path, egs_data_path, appid):
    """Return the path where a EGS game is installed."""
    appmanifest = get_appmanifest_from_appid(egs_data_path, appid)
    if not appmanifest:
        return None    
    return get_unix_path(prefix_path, appmanifest.installdir)


def get_appmanifests(egs_data_path):
    """Return the list for all appmanifest files in a EGS library folder"""
    metadata_dir = os.path.join(egs_data_path, 'Manifests')
    return glob.glob("{dir}/*.item".format(dir=metadata_dir))


def get_unix_path(prefix_path, windows_path):
        # TODO: duplicated code from WineRegistry to avoid some overhead. Consolidate at some point?
        windows_path = windows_path.replace("\\", "/")
        drives_path = os.path.join(prefix_path, "dosdevices")
        if not path_exists(drives_path):
            return
        letter, relpath = windows_path.split(":", 1)
        relpath = relpath.strip("/")
        drive_link = os.path.join(drives_path, letter.lower() + ":")
        try:
            drive_path = os.readlink(drive_link)
        except FileNotFoundError:
            logger.error("Unable to read link for %s", drive_link)
            return

        if not os.path.isabs(drive_path):
            drive_path = os.path.join(drives_path, drive_path)
        full_path = os.path.join(drive_path, relpath)
        return os.path.abspath(fix_path_case(full_path))
