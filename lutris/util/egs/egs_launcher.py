"""Interact with an exiting EGS install"""
import json
import os


class EGSLauncher:
    manifests_paths = 'ProgramData/Epic/EpicGamesLauncher/Data/Manifests'

    def __init__(self, prefix_path):
        self.prefix_path = prefix_path

    def iter_manifests(self):
        manifests_path = os.path.join(self.prefix_path, 'drive_c', self.manifests_paths)
        for manifest in os.listdir(manifests_path):
            if not manifest.endswith(".item"):
                continue
            with open(os.path.join(manifests_path, manifest)) as manifest_file:
                manifest_content = json.loads(manifest_file.read())
            if manifest_content["MainGameAppName"] != manifest_content["AppName"]:
                continue
            yield manifest_content
