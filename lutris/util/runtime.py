import os
from lutris import settings
from lutris.util import http
from lutris.util import extract
from lutris.util import system
from lutris.util.log import logger

LOCAL_VERSION_PATH = os.path.join(settings.RUNTIME_DIR, "VERSION")


def parse_version(version_content):
    try:
        version = int(version_content)
    except (ValueError, TypeError):
        version = 0
    return version


def get_local_version():
    if not os.path.exists(LOCAL_VERSION_PATH):
        return 0
    with open(LOCAL_VERSION_PATH, 'r') as version_file:
        version_content = version_file.read().strip()
    return parse_version(version_content)


def get_remote_version():
    version_url = settings.RUNTIME_URL + "VERSION"
    version_content = http.download_content(version_url)
    return parse_version(version_content)


def update_runtime(set_status):
    logger.debug("Updating runtime")
    remote_version = get_remote_version()
    local_version = get_local_version()
    if remote_version <= local_version:
        logger.debug("Runtime already up to date")
        return
    runtime32_file = "steam-runtime_32.tar.gz"
    runtime64_file = "steam-runtime_64.tar.gz"

    # Download
    set_status("Updating Runtime")
    runtime32_path = os.path.join(settings.RUNTIME_DIR, runtime32_file)
    http.download_asset(settings.RUNTIME_URL + runtime32_file, runtime32_path,
                        overwrite=True)
    runtime64_path = os.path.join(settings.RUNTIME_DIR, runtime64_file)
    http.download_asset(settings.RUNTIME_URL + runtime64_file, runtime64_path,
                        overwrite=True)
    # Remove current
    system.remove_folder(os.path.join(settings.RUNTIME_DIR, 'steam'))
    # Remove legacy folders
    system.remove_folder(os.path.join(settings.RUNTIME_DIR, 'lib32'))
    system.remove_folder(os.path.join(settings.RUNTIME_DIR, 'lib64'))

    # Extract
    extract.extract_archive(runtime32_path, settings.RUNTIME_DIR,
                            merge_single=False)
    extract.extract_archive(runtime64_path, settings.RUNTIME_DIR,
                            merge_single=False)
    os.unlink(runtime32_path)
    os.unlink(runtime64_path)

    with open(LOCAL_VERSION_PATH, 'w') as version_file:
        version_file.write(str(remote_version))
    set_status("Runtime updated")
    logger.debug("Runtime updated")


def get_runtime_env():
    """Return a dict containing LD_LIBRARY_PATH and STEAM_RUNTIME env vars.

    Ready for use! (Batteries not included (but not necessary))
    """
    runtime_dir = os.path.join(settings.RUNTIME_DIR, 'steam')
    ld_library_path = ':'.join(get_runtime_paths()) + ':$LD_LIBRARY_PATH'
    return {'STEAM_RUNTIME': runtime_dir, 'LD_LIBRARY_PATH': ld_library_path}


def get_runtime_paths():
    """Return a list of paths containing the runtime libraries."""
    runtime_dir = os.path.join(settings.RUNTIME_DIR, 'steam')
    paths = ["/lutris-override32",
             "/i386/lib/i386-linux-gnu",
             "/i386/lib",
             "/i386/usr/lib/i386-linux-gnu",
             "/i386/usr/lib"]
    paths = [runtime_dir + path for path in paths]

    if system.is_64bit:
        paths_64 = ["/lutris-override64",
                    "/amd64/lib/x86_64-linux-gnu",
                    "/amd64/lib",
                    "/amd64/usr/lib/x86_64-linux-gnu",
                    "/amd64/usr/lib"]
        paths_64 = [runtime_dir + path for path in paths_64]
        paths += paths_64
    return paths

