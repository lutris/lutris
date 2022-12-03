# pylint: disable=no-member
import struct
from io import BytesIO

try:
    import pefile
    PEFILE_AVAILABLE = True
except ImportError:
    pefile = None
    PEFILE_AVAILABLE = False

from PIL import Image

# From https://github.com/firodj/extract-icon-py


class ExtractIcon(object):
    GRPICONDIRENTRY_format = ('GRPICONDIRENTRY',
                              ('B,Width', 'B,Height', 'B,ColorCount', 'B,Reserved',
                               'H,Planes', 'H,BitCount', 'I,BytesInRes', 'H,ID'))
    GRPICONDIR_format = ('GRPICONDIR',
                         ('H,Reserved', 'H,Type', 'H,Count'))
    RES_ICON = 1
    RES_CURSOR = 2

    def __init__(self, filepath):
        self.pe = pefile.PE(filepath)

    def find_resource_base(self, res_type):
        rt_base_idx = [entry.id for
                       entry in self.pe.DIRECTORY_ENTRY_RESOURCE.entries].index(
            pefile.RESOURCE_TYPE[res_type]
        )

        if rt_base_idx is not None:
            return self.pe.DIRECTORY_ENTRY_RESOURCE.entries[rt_base_idx]

        return None

    def find_resource(self, res_type, res_index):
        rt_base_dir = self.find_resource_base(res_type)

        if res_index < 0:
            try:
                idx = [entry.id for entry in rt_base_dir.directory.entries].index(-res_index)
            except:
                return None
        else:
            idx = res_index if res_index < len(rt_base_dir.directory.entries) else None

        if idx is None:
            return None

        test_res_dir = rt_base_dir.directory.entries[idx]
        res_dir = test_res_dir
        if test_res_dir.struct.DataIsDirectory:
            # another Directory
            # probably language take the first one
            res_dir = test_res_dir.directory.entries[0]
        if res_dir.struct.DataIsDirectory:
            # Ooooooooooiconoo no !! another Directory !!!
            return None

        return res_dir

    def get_group_icons(self):
        rt_base_dir = self.find_resource_base('RT_GROUP_ICON')
        groups = []
        for res_index in range(0, len(rt_base_dir.directory.entries)):
            grp_icon_dir_entry = self.find_resource('RT_GROUP_ICON', res_index)

            if not grp_icon_dir_entry:
                continue

            data_rva = grp_icon_dir_entry.data.struct.OffsetToData
            size = grp_icon_dir_entry.data.struct.Size
            data = self.pe.get_memory_mapped_image()[data_rva:data_rva + size]
            file_offset = self.pe.get_offset_from_rva(data_rva)

            grp_icon_dir = pefile.Structure(self.GRPICONDIR_format, file_offset=file_offset)
            grp_icon_dir.__unpack__(data)

            if grp_icon_dir.Reserved != 0 or grp_icon_dir.Type != self.RES_ICON:
                continue
            offset = grp_icon_dir.sizeof()

            entries = []
            for _idx in range(0, grp_icon_dir.Count):
                grp_icon = pefile.Structure(self.GRPICONDIRENTRY_format, file_offset=file_offset + offset)
                grp_icon.__unpack__(data[offset:])
                offset += grp_icon.sizeof()
                entries.append(grp_icon)

            groups.append(entries)
        return groups

    def get_icon(self, index):
        icon_entry = self.find_resource('RT_ICON', -index)
        if not icon_entry:
            return None

        data_rva = icon_entry.data.struct.OffsetToData
        size = icon_entry.data.struct.Size
        data = self.pe.get_memory_mapped_image()[data_rva:data_rva + size]

        return data

    def export_raw(self, entries, index=None):
        if index is not None:
            entries = entries[index:index + 1]

        ico = struct.pack('<HHH', 0, self.RES_ICON, len(entries))
        data_offset = None
        data = []
        info = []
        for grp_icon in entries:
            if data_offset is None:
                data_offset = len(ico) + ((grp_icon.sizeof() + 2) * len(entries))

            nfo = grp_icon.__pack__()[:-2] + struct.pack('<L', data_offset)
            info.append(nfo)

            raw_data = self.get_icon(grp_icon.ID)
            if not raw_data:
                continue

            data.append(raw_data)
            data_offset += len(raw_data)

        raw = ico + b''.join(info + data)
        return raw

    def export(self, entries, index=None):
        raw = self.export_raw(entries, index)
        return Image.open(BytesIO(raw))

    def _get_bmp_header(self, data):
        if data[0:4] == b'\x89PNG':
            header = b''
        else:
            dib_size = struct.unpack('<L', data[0:4])[0]
            header = b'BM' + struct.pack('<LLL', len(data) + 14, 0, 14 + dib_size)
        return header
