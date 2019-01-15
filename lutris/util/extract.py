import os
import uuid
import shutil
import tarfile
import subprocess
import gzip
import zlib
from lutris.util import system
from lutris.util.log import logger
from lutris import settings


class ExtractFailure(Exception):
    """Exception raised when and archive fails to extract"""


def is_7zip_supported(path, extractor):
    supported_extractors = (
        "7z",
        "xz",
        "bzip2",
        "gzip",
        "tar",
        "zip",
        "ar",
        "arj",
        "cab",
        "chm",
        "cpio",
        "cramfs",
        "dmg",
        "ext",
        "fat",
        "gpt",
        "hfs",
        "ihex",
        "iso",
        "lzh",
        "lzma",
        "mbr",
        "msi",
        "nsis",
        "ntfs",
        "qcow2",
        "rar",
        "rpm",
        "squashfs",
        "udf",
        "uefi",
        "vdi",
        "vhd",
        "vmdk",
        "wim",
        "xar",
        "z",
    )
    if extractor:
        return extractor.lower() in supported_extractors
    _base, ext = os.path.splitext(path)
    if ext:
        ext = ext.lstrip(".").lower()
        return ext in supported_extractors


def extract_archive(path, to_directory=".", merge_single=True, extractor=None):
    path = os.path.abspath(path)
    mode = None
    logger.debug("Extracting %s to %s", path, to_directory)

    if path.endswith(".tar.gz") or path.endswith(".tgz") or extractor == "tgz":
        opener, mode = tarfile.open, "r:gz"
    elif path.endswith(".tar.xz") or path.endswith(".txz") or extractor == "txz":
        opener, mode = tarfile.open, "r:xz"
    elif path.endswith(".tar") or extractor == "tar":
        opener, mode = tarfile.open, "r:"
    elif path.endswith(".gz") or extractor == "gzip":
        decompress_gz(path, to_directory)
        return
    elif path.endswith(".tar.bz2") or path.endswith(".tbz") or extractor == "bz2":
        opener, mode = tarfile.open, "r:bz2"
    elif is_7zip_supported(path, extractor):
        opener = "7zip"
    else:
        raise RuntimeError(
            "Could not extract `%s` as no appropriate extractor is found" % path
        )
    temp_name = ".extract-" + str(uuid.uuid4())[:8]
    temp_path = temp_dir = os.path.join(to_directory, temp_name)
    try:
        _do_extract(path, temp_path, opener, mode, extractor)
    except (OSError, zlib.error) as ex:
        logger.exception("Extraction failed: %s", ex)
        raise ExtractFailure(str(ex))
    if merge_single:
        extracted = os.listdir(temp_path)
        if len(extracted) == 1:
            temp_path = os.path.join(temp_path, extracted[0])

    if os.path.isfile(temp_path):
        destination_path = os.path.join(to_directory, extracted[0])
        if os.path.isfile(destination_path):
            logger.warning("Overwrite existing file %s", destination_path)
            os.remove(destination_path)
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
                    system.merge_folders(source_path, destination_path)
            else:
                shutil.move(source_path, destination_path)
        system.remove_folder(temp_dir)
    logger.debug("Finished extracting %s to %s", path, to_directory)
    return path, to_directory


def _do_extract(archive, dest, opener, mode=None, extractor=None):
    if opener == "7zip":
        extract_7zip(archive, dest, archive_type=extractor)
    else:
        handler = opener(archive, mode)
        handler.extractall(dest)
        handler.close()


def decompress_gz(file_path, dest_path=None):
    """Decompress a gzip file."""
    if dest_path:
        dest_filename = os.path.join(dest_path, os.path.basename(file_path[:-3]))
    else:
        dest_filename = file_path[:-3]

    gzipped_file = gzip.open(file_path, "rb")
    file_content = gzipped_file.read()
    gzipped_file.close()

    dest_file = open(dest_filename, "wb")
    dest_file.write(file_content)
    dest_file.close()

    return dest_path


def extract_7zip(path, dest, archive_type=None):
    _7zip_path = os.path.join(settings.RUNTIME_DIR, "p7zip/7z")
    if not system.path_exists(_7zip_path):
        _7zip_path = system.find_executable("7z")
    if not system.path_exists(_7zip_path):
        raise OSError("7zip is not found in the lutris runtime or on the system")
    command = [_7zip_path, "x", path, "-o{}".format(dest), "-aoa"]
    if archive_type:
        command.append("-t{}".format(archive_type))
    subprocess.call(command)
