import os
from lutris.util import http
from lutris.util import extract
from lutris import settings

LOCAL_VERSION_PATH = os.path.join(settings.RUNTIME_DIR, "VERSION")


def parse_version(version_content):
    try:
        version = int(version_content)
    except ValueError:
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


def update_runtime():
    remote_version = get_remote_version()
    local_version = get_local_version()
    if remote_version <= local_version:
        return
    runtime32_file = "lutris-runtime-i386.tar.gz"
    runtime64_file = "lutris-runtime-amd64.tar.gz"

    runtime32_path = os.path.join(settings.RUNTIME_DIR, runtime32_file)
    http.download_asset(settings.RUNTIME_URL + runtime32_file, runtime32_path,
                        overwrite=True)
    runtime64_path = os.path.join(settings.RUNTIME_DIR, runtime64_file)
    http.download_asset(settings.RUNTIME_URL + runtime64_file, runtime64_path,
                        overwrite=True)
    extract.extract_archive(runtime32_path, settings.RUNTIME_DIR,
                            merge_single=False)
    extract.extract_archive(runtime64_path, settings.RUNTIME_DIR,
                            merge_single=False)
    os.unlink(runtime32_path)
    os.unlink(runtime64_path)

    with open(LOCAL_VERSION_PATH, 'w') as version_file:
        version_file.write(str(remote_version))
