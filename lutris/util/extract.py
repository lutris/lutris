import gzip
import os
import shutil
import subprocess
import tarfile
import uuid
import zipfile
import zlib

from lutris import settings
from lutris.exceptions import MissingExecutableError
from lutris.util import system
from lutris.util.log import logger


class ExtractError(Exception):
    """Exception raised when and archive fails to extract"""


def extract_archive(path: str, to_directory: str = ".", merge_single: bool = True, extractor=None) -> tuple[str, str]:
    """Extract an archive to a destination directory.

    Args:
        path: Absolute or relative path to the archive file.
        to_directory: Directory to extract into. Extracted files end up directly
            in this directory (not in a subdirectory), unless merge_single is False.
        merge_single: When True and the archive contains a single top-level directory,
            that directory's contents are merged into to_directory instead of creating
            a nested folder. When True and the archive contains a single file that is
            itself an archive, it is automatically extracted recursively. Set to False
            to extract the archive structure as-is.
        extractor: Force a specific extractor (e.g. "tgz", "7zip", "gog"). When None,
            the extractor is guessed from the file extension.

    Returns:
        A tuple of (archive_path, to_directory).
    """
    path = os.path.abspath(path)
    logger.debug("Extracting %s to %s", path, to_directory)

    if extractor is None:
        extractor = _guess_extractor(path)

    opener, mode = _get_archive_opener(extractor)

    temp_path = temp_dir = os.path.join(to_directory, ".extract-%s" % _random_id())
    try:
        _do_extract(path, temp_path, opener, mode, extractor)
    except (OSError, zlib.error, tarfile.ReadError, EOFError) as ex:
        logger.error("Extraction failed: %s", ex)
        raise ExtractError(str(ex)) from ex
    if merge_single:
        extracted = os.listdir(temp_path)
        if len(extracted) == 1:
            temp_path = os.path.join(temp_path, extracted[0])

    if os.path.isfile(temp_path):
        # If extraction produced a single file that is itself an archive
        # (e.g. tar.gz-wrapped zip from GameJolt), extract it recursively.
        inner_extractor = _guess_extractor(temp_path)
        # These aren't real archives — extracting them just copies the file,
        # so treating them as nested archives would cause infinite recursion.
        if inner_extractor in ("exe", "AppImage"):
            inner_extractor = None
        if inner_extractor is None:
            if tarfile.is_tarfile(temp_path):
                inner_extractor = "tar"
            elif zipfile.is_zipfile(temp_path):
                inner_extractor = "auto"
        if inner_extractor:
            logger.debug("Nested archive detected (%s), extracting inner layer", inner_extractor)
            try:
                return extract_archive(temp_path, to_directory, merge_single, inner_extractor)
            finally:
                system.delete_folder(temp_dir)

        destination_path = os.path.join(to_directory, extracted[0])
        if os.path.isfile(destination_path):
            logger.warning("Overwrite existing file %s", destination_path)
            os.remove(destination_path)
        if os.path.isdir(destination_path):
            os.rename(destination_path, destination_path + _random_id())

        shutil.move(temp_path, to_directory)
        os.removedirs(temp_dir)
    else:
        for archive_file in os.listdir(temp_path):
            source_path = os.path.join(temp_path, archive_file)
            destination_path = os.path.join(to_directory, archive_file)
            # logger.debug("Moving extracted files from %s to %s", source_path, destination_path)

            if system.path_exists(destination_path):
                logger.warning("Overwrite existing path %s", destination_path)
                if os.path.isfile(destination_path):
                    os.remove(destination_path)
                    shutil.move(source_path, destination_path)
                elif os.path.isdir(destination_path):
                    try:
                        system.merge_folders(source_path, destination_path)
                    except OSError as ex:
                        logger.error(
                            "Failed to merge to destination %s: %s",
                            destination_path,
                            ex,
                        )
                        raise ExtractError(str(ex)) from ex
            else:
                shutil.move(source_path, destination_path)
        system.delete_folder(temp_dir)
    logger.debug("Finished extracting %s to %s", path, to_directory)
    return path, to_directory


def _guess_extractor(path):
    """Guess what extractor should be used from a file name"""
    if path.endswith(".tar"):
        extractor = "tar"
    elif path.endswith((".tar.gz", ".tgz")):
        extractor = "tgz"
    elif path.endswith((".tar.xz", ".txz", ".tar.lzma")):
        extractor = "txz"
    elif path.endswith((".tar.bz2", ".tbz2", ".tbz")):
        extractor = "tbz2"
    elif path.endswith((".tar.zst", ".tzst")):
        extractor = "tzst"
    elif path.endswith(".gz"):
        extractor = "gzip"
    elif path.endswith(".exe"):
        extractor = "exe"
    elif path.endswith(".deb"):
        extractor = "deb"
    elif path.casefold().endswith(".appimage"):
        extractor = "AppImage"
    else:
        extractor = None
    return extractor


def _get_archive_opener(extractor):
    """Return the archive opener and optional mode for an extractor"""
    mode = None
    if extractor == "tar":
        opener, mode = tarfile.open, "r:"
    elif extractor == "tgz":
        opener, mode = tarfile.open, "r:gz"
    elif extractor == "txz":
        opener, mode = tarfile.open, "r:xz"
    elif extractor in ("tbz2", "bz2"):  # bz2 is used for .tar.bz2 in some installer scripts
        opener, mode = tarfile.open, "r:bz2"
    elif extractor == "tzst":
        opener, mode = tarfile.open, "r:zst"  # Note: not supported by tarfile yet
    elif extractor == "gzip":
        opener = "gz"
    elif extractor == "gog":
        opener = "innoextract"
    elif extractor == "exe":
        opener = "exe"
    elif extractor == "deb":
        opener = "deb"
    elif extractor == "AppImage":
        opener = "AppImage"
    else:
        opener = "7zip"
    return opener, mode


def _random_id():
    """Return a random ID"""
    return str(uuid.uuid4())[:8]


def _do_extract(archive: str, dest: str, opener, mode: str | None = None, extractor=None) -> None:
    if opener == "gz":
        _decompress_gz(archive, dest)
    elif opener == "7zip":
        _extract_7zip(archive, dest, archive_type=extractor)
    elif opener == "exe":
        _extract_exe(archive, dest)
    elif opener == "innoextract":
        _extract_gog(archive, dest)
    elif opener == "deb":
        _extract_deb(archive, dest)
    elif opener == "AppImage":
        _extract_AppImage(archive, dest)
    else:
        handler = opener(archive, mode)
        handler.extractall(dest)
        handler.close()


def _decompress_gz(file_path: str, dest_path: str):
    """Decompress a gzip file."""
    if dest_path:
        dest_filename = os.path.join(dest_path, os.path.basename(file_path[:-3]))
    else:
        dest_filename = file_path[:-3]
    os.makedirs(os.path.dirname(dest_filename), exist_ok=True)

    with open(dest_filename, "wb") as dest_file:
        gzipped_file = gzip.open(file_path, "rb")
        dest_file.write(gzipped_file.read())
        gzipped_file.close()


def _extract_7zip(path: str, dest: str, archive_type: str | None = None) -> None:
    _7zip_path = _get_7zip_path()
    command = [_7zip_path, "x", path, "-o{}".format(dest), "-aoa"]
    if archive_type and archive_type != "auto":
        command.append("-t{}".format(archive_type))
    subprocess.call(command)


def _get_7zip_path() -> str:
    """Return the path where 7zip is installed"""
    for bin_name in ["7z", "7za"]:
        _7zip_path = os.path.join(settings.RUNTIME_DIR, f"p7zip/{bin_name}")
        if system.path_exists(_7zip_path):
            return _7zip_path
    logger.warning("7z/7za not available in the runtime folder, using system version")
    try:
        return system.find_required_executable("7z")
    except MissingExecutableError:
        return system.find_required_executable("7za")


def _extract_exe(path: str, dest: str) -> None:
    if _check_inno_exe(path):
        _decompress_gog(path, dest)
    else:
        # use 7za to check if exe is an archive
        _7zip_path = _get_7zip_path()
        command = [_7zip_path, "t", path]
        return_code = subprocess.call(command)
        if return_code == 0:
            _extract_7zip(path, dest)
        else:
            raise RuntimeError("specified exe is not an archive or GOG setup file")


def _check_inno_exe(path) -> bool:
    """Check if a path in a compatible innosetup archive"""
    try:
        innoextract_path = _get_innoextract_path()
    except MissingExecutableError:
        logger.warning("Innoextract not found, can't determine type of archive %s", path)
        return False

    command = [innoextract_path, "-i", path]
    return_code = subprocess.call(command)
    return return_code == 0


def _decompress_gog(file_path: str, destination_path: str) -> None:
    innoextract_path = _get_innoextract_path()
    system.create_folder(destination_path)  # innoextract cannot do mkdir -p
    process = subprocess.run(
        [innoextract_path, "-m", "-g", "-d", destination_path, "-e", file_path], capture_output=True
    )
    if process.returncode != 0:
        stderr = process.stderr.decode().strip()
        logger.error("Innoextract failed to extract GOG setup file: %s", stderr)
        raise RuntimeError("innoextract failed to extract GOG setup file")


def _get_innoextract_path() -> str:
    """Return the path where innoextract is installed"""
    inno_dirs = [path for path in os.listdir(settings.RUNTIME_DIR) if path.startswith("innoextract")]
    for inno_dir in inno_dirs:
        inno_path = os.path.join(settings.RUNTIME_DIR, inno_dir, "innoextract")
        if system.path_exists(inno_path):
            return inno_path

    inno_path = system.find_required_executable("innoextract")
    logger.warning("innoextract not available in the runtime folder, using some random version")
    return inno_path


def _extract_gog(path: str, dest: str) -> None:
    if _check_inno_exe(path):
        _decompress_gog(path, dest)
    else:
        raise RuntimeError("specified exe is not a GOG setup file")


def _extract_deb(archive: str, dest: str) -> None:
    """Extract the contents of a deb file to a destination folder"""
    _extract_7zip(archive, dest, archive_type="ar")
    debian_folder = os.path.join(dest, "debian")
    os.makedirs(debian_folder)

    control_file_exts = [".gz", ".xz", ".zst", ""]
    for extension in control_file_exts:
        control_tar_path = os.path.join(dest, "control.tar{}".format(extension))
        if os.path.exists(control_tar_path):
            shutil.move(control_tar_path, debian_folder)
            break

    data_file_exts = [".gz", ".xz", ".zst", ".bz2", ".lzma", ""]
    for extension in data_file_exts:
        data_tar_path = os.path.join(dest, "data.tar{}".format(extension))
        if os.path.exists(data_tar_path):
            extract_archive(data_tar_path, dest)
            os.remove(data_tar_path)
            break


def _extract_AppImage(path: str, dest: str) -> None:
    """This is really here to prevent 7-zip from extracting the AppImage;
    we want to just use this sort of file as-is."""
    system.create_folder(dest)
    shutil.copy(path, dest)


def get_innoextract_list(file_path: str) -> list[str]:
    """Return the list of files contained in a GOG archive"""
    output = system.read_process_output([_get_innoextract_path(), "-lmq", file_path])
    return [line[3:] for line in output.split("\n") if line]
