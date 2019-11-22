"""EGS appmanifest file hnadling"""
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


def get_path_from_appmanifest(egs_data_path, appid):
    """Return the path where a EGS game is installed."""
    appmanifest = get_appmanifest_from_appid(egs_data_path, appid)
    if not appmanifest:
        return None
    return appmanifest.get_install_path()


def get_appmanifests(egs_data_path):
    """Return the list for all appmanifest files in a EGS library folder"""
    metadata_dir = os.path.join(egs_data_path, 'Manifests')
    return glob.glob(f"{metadata_dir}/*.item")
