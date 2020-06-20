# Standard Library
import errno
import gzip
import os
import shutil
import subprocess
import tarfile
import uuid
import zlib

# Lutris Modules
from lutris import settings
from lutris.util import system
from lutris.util.log import logger


class ExtractFailure(Exception):

    """Exception raised when and archive fails to extract"""


def random_id():
    """Return a random ID"""
    return str(uuid.uuid4())[:8]


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


def guess_extractor(path):
    """Guess what extractor should be used from a file name"""
    if path.endswith(".tar.gz") or path.endswith(".tgz"):
        extractor = "tgz"
    elif path.endswith(".tar.xz") or path.endswith(".txz"):
        extractor = "txz"
    elif path.endswith(".tar"):
        extractor = "tar"
    elif path.endswith(".tar.bz2") or path.endswith(".tbz"):
        extractor = "bz2"
    elif path.endswith(".gz"):
        extractor = "gzip"
    elif path.endswith(".exe"):
        extractor = "exe"
    elif is_7zip_supported(path, None):
        extractor = None
    else:
        raise RuntimeError("Could not extract `%s` - no appropriate extractor found" % path)
    return extractor


def get_archive_opener(extractor, path):
    """Return the archive opener and optional mode for an extractor"""
    mode = None
    if extractor == "tgz":
        opener, mode = tarfile.open, "r:gz"
    elif extractor == "txz":
        opener, mode = tarfile.open, "r:xz"
    elif extractor == "tar":
        opener, mode = tarfile.open, "r:"
    elif extractor == "bz2":
        opener, mode = tarfile.open, "r:bz2"
    elif extractor == "gzip":
        opener = "gz"
    elif extractor == "gog":
        opener = "innoextract"
    elif extractor == "exe":
        opener = "exe"
    elif extractor is None or is_7zip_supported(path, extractor):
        opener = "7zip"
    else:
        raise RuntimeError("Could not extract `%s` - unknown format specified" % path)
    return opener, mode


def extract_archive(path, to_directory=".", merge_single=True, extractor=None):
    path = os.path.abspath(path)
    logger.debug("Extracting %s to %s", path, to_directory)

    if extractor is None:
        extractor = guess_extractor(path)

    opener, mode = get_archive_opener(extractor, path)

    temp_name = ".extract-" + random_id()
    temp_path = temp_dir = os.path.join(to_directory, temp_name)
    try:
        _do_extract(path, temp_path, opener, mode, extractor)
    except (OSError, zlib.error, tarfile.ReadError, EOFError) as ex:
        logger.error("Extraction failed: %s", ex)
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
        if os.path.isdir(destination_path):
            os.rename(destination_path, destination_path + random_id())

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
                        raise ExtractFailure(str(ex))
            else:
                shutil.move(source_path, destination_path)
        system.remove_folder(temp_dir)
    logger.debug("Finished extracting %s to %s", path, to_directory)
    return path, to_directory


def _do_extract(archive, dest, opener, mode=None, extractor=None):
    if opener == "gz":
        decompress_gz(archive, dest)
    if opener == "7zip":
        extract_7zip(archive, dest, archive_type=extractor)
    elif opener == "exe":
        extract_exe(archive, dest)
    elif opener == "innoextract":
        extract_gog(archive, dest)
    else:
        handler = opener(archive, mode)
        handler.extractall(dest)
        handler.close()


def extract_exe(path, dest):
    if check_inno_exe(path):
        decompress_gog(path, dest)
    else:
        # use 7za to check if exe is an archive
        _7zip_path = os.path.join(settings.RUNTIME_DIR, "p7zip/7za")
        if not system.path_exists(_7zip_path):
            _7zip_path = system.find_executable("7za")
        if not system.path_exists(_7zip_path):
            raise OSError("7zip is not found in the lutris runtime or on the system")
        command = [_7zip_path, "t", path]
        return_code = subprocess.call(command)
        if return_code == 0:
            extract_7zip(path, dest)
        else:
            raise RuntimeError("specified exe is not an archive or GOG setup file")


def extract_gog(path, dest):
    if check_inno_exe(path):
        decompress_gog(path, dest)
    else:
        raise RuntimeError("specified exe is not a GOG setup file")


# Check if exe is in fact an inno setup file
def check_inno_exe(path):
    _innoextract_path = os.path.join(settings.RUNTIME_DIR, "innoextract/innoextract")
    if not system.path_exists(_innoextract_path):
        _innoextract_path = system.find_executable("innoextract")
    if not system.path_exists(_innoextract_path):
        return False  # Can't find innoextract
    command = [_innoextract_path, "-i", path]
    return_code = subprocess.call(command)
    if return_code != 0:
        return False
    return True


def decompress_gog(file_path, destination_path):
    _innoextract_path = os.path.join(settings.RUNTIME_DIR, "innoextract/innoextract")
    if not system.path_exists(_innoextract_path):
        _innoextract_path = system.find_executable("innoextract")
    if not system.path_exists(_innoextract_path):
        raise OSError("innoextract is not found in the lutris runtime or on the system")
    # innoextract cannot do mkdir -p, so we have to do it here:
    try:
        os.makedirs(destination_path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise OSError("cannot make output directory for extracting setup file")
    command = [_innoextract_path, "-g", "-d", destination_path, "-e", file_path]
    return_code = subprocess.call(command)
    if return_code != 0:
        raise RuntimeError("innoextract failed to extract GOG setup file")


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
