import os
import uuid
import shutil
import tarfile
import gzip
from lutris.util.system import merge_folders
from lutris.util.log import logger


def is_7zip_supported(path, extractor):
    supported_extractors = ('ar', 'arj', 'cab', 'chm', 'cpio', 'cramfs', 'dmg', 'ext',
                            'fat', 'gpt', 'hfs', 'ihex', 'iso', 'lzh', 'lzma', 'mbr',
                            'msi', 'nsis', 'ntfs', 'qcow2', 'rar', 'rpm', 'squashfs',
                            'udf', 'uefi', 'vdi', 'vhd', 'vmdk', 'wim', 'xar', 'z')
    if extractor:
        return extractor in supported_extractors
    else:
        _base, ext = os.path.splitext(path)
        if ext:
            ext = ext.lstrip('.').lower()
            return ext in supported_extractors


def extract_7zip(path):
    raise NotImplementedError


def extract_archive(path, to_directory='.', merge_single=True, extractor=None):
    path = os.path.abspath(path)
    logger.debug("Extracting %s to %s", path, to_directory)
    if(path.endswith('.tar.gz') or path.endswith('.tgz')
       or extractor == 'tgz'):
        opener, mode = tarfile.open, 'r:gz'
    elif path.endswith('.gz') or extractor == 'gzip':
        decompress_gz(path, to_directory)
        return
    elif(path.endswith('.tar.bz2') or path.endswith('.tbz')
         or extractor == 'bz2'):
        opener, mode = tarfile.open, 'r:bz2'
    elif(is_7zip_supported(path, extractor)):
        opener = extract_7zip
    else:
        raise RuntimeError(
            "Could not extract `%s` as no appropriate extractor is found"
            % path)
    temp_name = ".extract-" + str(uuid.uuid4())[:8]
    temp_path = temp_dir = os.path.join(to_directory, temp_name)
    handler = opener(path, mode)
    handler.extractall(temp_path)
    handler.close()
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
        for f in os.listdir(temp_path):
            logger.debug("Moving element %s of archive", f)
            source_path = os.path.join(temp_path, f)
            destination_path = os.path.join(to_directory, f)
            if os.path.exists(destination_path):
                logger.warning("Overwrite existing path %s", destination_path)
                if os.path.isfile(destination_path):
                    os.remove(destination_path)
                    shutil.move(source_path, destination_path)
                elif os.path.isdir(destination_path):
                    merge_folders(source_path, destination_path)
            else:
                shutil.move(source_path, destination_path)
        shutil.rmtree(temp_dir)
    logger.debug("Finished extracting %s", path)
    return (path, to_directory)


def decompress_gz(file_path, dest_path=None):
    """Decompress a gzip file."""
    if dest_path:
        dest_filename = os.path.join(dest_path,
                                     os.path.basename(file_path[:-3]))
    else:
        dest_filename = file_path[:-3]

    gzipped_file = gzip.open(file_path, 'rb')
    file_content = gzipped_file.read()
    gzipped_file.close()

    dest_file = open(dest_filename, 'wb')
    dest_file.write(file_content)
    dest_file.close()

    return dest_path
