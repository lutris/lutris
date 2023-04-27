"""DXVK helper module"""
import os
import shutil

from lutris import api
from lutris.settings import RUNTIME_DIR
from lutris.util.extract import extract_archive
from lutris.util.graphics import vkquery
from lutris.util.http import download_file
from lutris.util.log import logger
from lutris.util.system import create_folder, execute, remove_folder
from lutris.util.wine.dll_manager import DLLManager

REQUIRED_VULKAN_API_VERSION = vkquery.vk_make_version(1, 3, 0)


class DXVKManager(DLLManager):
    component = "DXVK"
    base_dir = os.path.join(RUNTIME_DIR, "dxvk")
    versions_path = os.path.join(base_dir, "dxvk_versions.json")
    managed_dlls = ("dxgi", "d3d11", "d3d10core", "d3d9",)
    releases_url = "https://api.github.com/repos/lutris/dxvk/releases"
    vulkan_api_version = vkquery.get_expected_api_version()

    def is_recommended_version(self, version):
        # DXVK 2.x and later require Vulkan 1.3, so if that iss lacking
        # we default to 1.x.
        if self.vulkan_api_version and self.vulkan_api_version < REQUIRED_VULKAN_API_VERSION:
            return version.startswith("v1.")
        return super().is_recommended_version(version)

    @staticmethod
    def is_managed_dll(dll_path):
        """Check if a given DLL path is provided by the component

        Very basic check to see if a dll contains the string "dxvk".
        """
        try:
            with open(dll_path, 'rb') as file:
                prev_block_end = b''
                while True:
                    block = file.read(2 * 1024 * 1024)  # 2 MiB
                    if not block:
                        break
                    if b'dxvk' in prev_block_end + block[:4]:
                        return True
                    if b'dxvk' in block:
                        return True

                    prev_block_end = block[-4:]
        except OSError:
            pass
        return False


def update_shader_cache(game):
    state_cache_path = game.config.system_config["env"]["DXVK_STATE_CACHE_PATH"]
    if not os.path.exists(state_cache_path):
        logger.warning("%s is not a valid path", state_cache_path)
        return False
    game_details = api.get_game_details(game.slug)
    if not game_details.get("shaders"):
        logger.debug("No shaders for %s", game)
        return False
    last_updated_local = game.config.game_config.get("dxvk_cache_updated_at")
    most_recent_update = None
    shader_url = None
    for shader in game_details["shaders"]:
        if not most_recent_update or most_recent_update < shader["updated_at"]:
            shader_url = shader["url"]
            most_recent_update = shader["updated_at"]
    if last_updated_local and last_updated_local >= most_recent_update:
        logger.debug("Cache up to date")
        return False
    shader_merge_path = os.path.join(state_cache_path, "dxvk-state-cache")
    create_folder(shader_merge_path)
    shader_archive_path = os.path.join(shader_merge_path, os.path.basename(shader_url))
    download_file(shader_url, shader_archive_path)
    extract_archive(shader_archive_path, to_directory=shader_merge_path)
    try:
        remote_cache_path = [
            shader_file for shader_file in os.listdir(shader_merge_path)
            if shader_file.endswith(".dxvk-cache")
        ][0]
    except IndexError:
        logger.error("Cache path not found")
        return False
    cache_file_name = os.path.basename(remote_cache_path)
    local_cache_path = os.path.join(state_cache_path, cache_file_name)
    if not os.path.exists(local_cache_path):
        shutil.copy(remote_cache_path, state_cache_path)
    else:
        local_copy_path = os.path.join(shader_merge_path, "Local.dxvk-cache")
        output_path = os.path.join(shader_merge_path, "output.dxvk-cache")
        shutil.copy(local_cache_path, local_copy_path)
        state_merge_tool_path = os.path.join(RUNTIME_DIR, "dxvk-cache-tool/dxvk_cache_tool")
        if not os.path.exists(state_merge_tool_path):
            logger.error("dxvk_cache_tool not present")
            return False
        execute([
            state_merge_tool_path,
            remote_cache_path,
            local_copy_path
        ], cwd=shader_merge_path)
        if not os.path.exists(output_path):
            logger.error("Merging of shader failed")
        shutil.copy(output_path, local_cache_path)
    remove_folder(shader_merge_path)
    game.config.game_level["game"]["dxvk_cache_updated_at"] = most_recent_update
    game.config.save()
