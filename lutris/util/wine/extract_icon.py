"""
The MIT License (MIT)

Copyright (c) 2015-2016 Fadhil Mandaga
Copyright (c) 2019-2025 James Lu <james@overdrivenetworks.com>
Copyright (c) 2025 Hoang Cao Tri

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# pylint: disable=no-member
import logging
import struct
from io import BytesIO

from PIL import Image

try:
    import pefile

    PEFILE_AVAILABLE = True
except ImportError:
    pefile = None
    PEFILE_AVAILABLE = False

GRPICONDIRENTRY_FORMAT = (
    "GRPICONDIRENTRY",
    ("B,Width", "B,Height", "B,ColorCount", "B,Reserved", "H,Planes", "H,BitCount", "I,BytesInRes", "H,ID"),
)
GRPICONDIR_FORMAT = ("GRPICONDIR", ("H,Reserved", "H,Type", "H,Count"))

logger = logging.getLogger("icoextract")
logging.basicConfig()


class IconExtractorError(Exception):
    """Superclass for exceptions raised by IconExtractor."""


class IconNotFoundError(IconExtractorError):
    """Exception raised when extracting an icon index or resource ID that does not exist."""


class NoIconsAvailableError(IconExtractorError):
    """Exception raised when the input program has no icon resources."""


class InvalidIconDefinitionError(IconExtractorError):
    """Exception raised when the input program has an invalid icon resource."""


class IconExtractor:
    def __init__(self, filename=None, data=None):
        """
        Loads an executable from the given `filename` or `data` (raw bytes).
        As with pefile, if both `filename` and `data` are given, `filename` takes precedence.

        If the executable has contains no icons, this will raise `NoIconsAvailableError`.
        """
        # Use fast loading and explicitly load the RESOURCE directory entry. This saves a LOT of time
        # on larger files
        self._pe = pefile.PE(name=filename, data=data, fast_load=True)
        self._pe.parse_data_directories(pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"])

        if not hasattr(self._pe, "DIRECTORY_ENTRY_RESOURCE"):
            raise NoIconsAvailableError("File has no resources")

        # Reverse the list of entries before making the mapping so that earlier values take precedence
        # When an executable includes multiple icon resources, we should use only the first one.
        # pylint: disable=no-member
        resources = {rsrc.id: rsrc for rsrc in reversed(self._pe.DIRECTORY_ENTRY_RESOURCE.entries)}

        self.groupiconres = resources.get(pefile.RESOURCE_TYPE["RT_GROUP_ICON"])
        if not self.groupiconres:
            raise NoIconsAvailableError("File has no group icon resources")
        self.rticonres = resources.get(pefile.RESOURCE_TYPE["RT_ICON"])

        # Populate resources by ID
        self._group_icons = {entry.struct.Name: idx for idx, entry in enumerate(self.groupiconres.directory.entries)}
        self._icons = {
            icon_entry_list.id: icon_entry_list.directory.entries[0]  # Select first language
            for icon_entry_list in self.rticonres.directory.entries
        }

    def _get_icon(self, index: int = 0):
        """
        Returns the specified group icon in the binary.

        Result is a list of (group icon structure, icon data) tuples.
        """
        try:
            groupicon = self.groupiconres.directory.entries[index]
        except IndexError:
            raise IconNotFoundError(f"No icon exists at index {index}") from None
        resource_id = groupicon.struct.Name
        icon_lang = None
        if groupicon.struct.DataIsDirectory:
            # Select the first language from subfolders as needed.
            groupicon = groupicon.directory.entries[0]
            icon_lang = groupicon.struct.Name
            logger.debug("Picking first language %s", icon_lang)

        # Read the data pointed to by the group icon directory (GRPICONDIR) struct.
        rva = groupicon.data.struct.OffsetToData
        grp_icon_data = self._pe.get_data(rva, groupicon.data.struct.Size)
        file_offset = self._pe.get_offset_from_rva(rva)

        grp_icon_dir = self._pe.__unpack_data__(GRPICONDIR_FORMAT, grp_icon_data, file_offset)
        logger.debug(
            "Group icon %d has ID %s and %d images: %s",
            # pylint: disable=no-member
            index,
            resource_id,
            grp_icon_dir.Count,
            grp_icon_dir,
        )

        # pylint: disable=no-member
        if grp_icon_dir.Reserved:
            # pylint: disable=no-member
            raise InvalidIconDefinitionError(
                "Invalid group icon definition (got Reserved=%s instead of 0)" % hex(grp_icon_dir.Reserved)
            )

        # For each group icon entry (GRPICONDIRENTRY) that immediately follows, read the struct and look up the
        # corresponding icon image
        grp_icons = []
        icon_offset = grp_icon_dir.sizeof()
        for grp_icon_index in range(grp_icon_dir.Count):
            grp_icon = self._pe.__unpack_data__(
                GRPICONDIRENTRY_FORMAT, grp_icon_data[icon_offset:], file_offset + icon_offset
            )
            icon_offset += grp_icon.sizeof()
            logger.debug("Got group icon entry %d: %s", grp_icon_index, grp_icon)

            icon_entry = self._icons[grp_icon.ID]
            icon_data = self._pe.get_data(icon_entry.data.struct.OffsetToData, icon_entry.data.struct.Size)
            logger.debug("Got icon data for ID %d: %s", grp_icon.ID, icon_entry.data.struct)
            grp_icons.append((grp_icon, icon_data))
        return grp_icons

    def get_best_icon(self, size=128):
        """
        Extract best matching icon closest to specified size

        Returns PIL Image object or None if extraction fails
        """
        icons = self._get_icon()
        best_score = -1
        icon = None

        for grp_icon, icon_data in icons:
            width = grp_icon.Width or 256
            height = grp_icon.Height or 256
            bit_count = grp_icon.BitCount or 32

            score = (1 << 20) if (width == size and height == size) else (bit_count << 10) + (width * height)
            if score > best_score:
                best_score = score
                icon = (grp_icon, icon_data)
        if not icon:
            return None

        # Write minimal ICO header and icon data
        with BytesIO() as buffer:
            buffer.write(
                b"\x00\x00"  # 2 reserved bytes
                + struct.pack("<HH", 1, 1)  # 0x1 (little endian) specifying that this is an .ICO image
                +
                # Elements in ICONDIRENTRY and GRPICONDIRENTRY are all the same
                # except the last value, which is an ID in GRPICONDIRENTRY and
                # the offset from the beginning of the file in ICONDIRENTRY.
                icon[0].__pack__()[:12]  # ICONDIRENTRY
                + struct.pack("<I", 22)  # Data Offset
                + icon[1]  # Icon Data
            )
            buffer.seek(0)
            return Image.open(buffer)
        return None


__all__ = ["IconExtractor", "IconExtractorError", "InvalidIconDefinitionError", "NoIconsAvailableError"]
