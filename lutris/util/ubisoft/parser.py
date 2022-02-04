import logging as log
import math

import yaml

from lutris.util.ubisoft.consts import UBISOFT_CONFIGURATIONS_BLACKLISTED_NAMES


class UbisoftParser(object):
    def __init__(self):
        self.configuration_raw = None
        self.ownership_raw = None
        self.settings_raw = None
        self.parsed_games = None

    def _convert_data(self, data):
        # calculate object size (konrad's formula)
        if data > 256 * 256:
            data = data - (128 * 256 * math.ceil(data / (256 * 256)))
            data = data - (128 * math.ceil(data / 256))
        else:
            if data > 256:
                data = data - (128 * math.ceil(data / 256))
        return data

    def _parse_configuration_header(self, header, second_eight=False):
        try:
            offset = 1
            multiplier = 1
            record_size = 0
            tmp_size = 0

            if second_eight:
                while header[offset] != 0x08 or (header[offset] == 0x08 and header[offset + 1] == 0x08):
                    record_size += header[offset] * multiplier
                    multiplier *= 256
                    offset += 1
                    tmp_size += 1
            else:
                while header[offset] != 0x08 or record_size == 0:
                    record_size += header[offset] * multiplier
                    multiplier *= 256
                    offset += 1
                    tmp_size += 1

            record_size = self._convert_data(record_size)

            offset += 1  # skip 0x08

            # look for launch_id
            multiplier = 1
            launch_id = 0

            while header[offset] != 0x10 or header[offset + 1] == 0x10:
                launch_id += header[offset] * multiplier
                multiplier *= 256
                offset += 1

            launch_id = self._convert_data(launch_id)

            offset += 1  # skip 0x10

            multiplier = 1
            launch_id_2 = 0
            while header[offset] != 0x1A or (header[offset] == 0x1A and header[offset + 1] == 0x1A):
                launch_id_2 += header[offset] * multiplier
                multiplier *= 256
                offset += 1

            launch_id_2 = self._convert_data(launch_id_2)

            # if object size is smaller than 128b, there might be a chance that secondary size will not occupy 2b
            if record_size - offset < 128 <= record_size:
                tmp_size -= 1
                record_size += 1

            # we end up in the middle of header, return values normalized
            # to end of record as well real yaml size and game launch_id
            return record_size - offset, launch_id, launch_id_2, offset + tmp_size + 1
        except:
            # something went horribly wrong, do not crash it,
            # just return 0s, this way it will be handled later in the code
            # 10 is to step a little in configuration file in order to find next game
            return 0, 0, 0, 10

    def _parse_ownership_header(self, header):
        offset = 1
        multiplier = 1
        record_size = 0
        tmp_size = 0
        if header[offset - 1] == 0x0a:
            while header[offset] != 0x08 or record_size == 0:
                record_size += header[offset] * multiplier
                multiplier *= 256
                offset += 1
                tmp_size += 1

            record_size = self._convert_data(record_size)

            offset += 1  # skip 0x08

            # look for launch_id
            multiplier = 1
            launch_id = 0

            while header[offset] != 0x10 or header[offset + 1] == 0x10:
                launch_id += header[offset] * multiplier
                multiplier *= 256
                offset += 1

            launch_id = self._convert_data(launch_id)

            offset += 1  # skip 0x10

            multiplier = 1
            launch_id_2 = 0
            while header[offset] != 0x22:
                launch_id_2 += header[offset] * multiplier
                multiplier *= 256
                offset += 1

            launch_id_2 = self._convert_data(launch_id_2)
            return launch_id, launch_id_2, record_size + tmp_size + 1
        else:
            return None, None, None

    def _parse_configuration(self):
        configuration_content = self.configuration_raw
        global_offset = 0
        records = {}
        if configuration_content:
            try:
                while global_offset < len(configuration_content):
                    data = configuration_content[global_offset:]
                    object_size, install_id, launch_id, header_size = self._parse_configuration_header(data)

                    launch_id = install_id if launch_id == 0 or launch_id == install_id else launch_id

                    if object_size > 500:
                        records[install_id] = {
                            'size': object_size,
                            'offset': global_offset + header_size,
                            'install_id': install_id,
                            'launch_id': launch_id
                        }
                    global_offset_tmp = global_offset
                    global_offset += object_size + header_size

                    if global_offset < len(configuration_content) and configuration_content[global_offset] != 0x0A:
                        object_size, _, _, header_size = self._parse_configuration_header(data, True)
                        global_offset = global_offset_tmp + object_size + header_size
            except:
                log.exception("parse_configuration failed with exception. Possibly 'configuration' file corrupted")
        return records

    def _parse_ownership(self):
        ownership_content = self.ownership_raw
        global_offset = 0x108
        records = []
        try:
            while global_offset < len(ownership_content):
                data = ownership_content[global_offset:]
                launch_id, launch_id2, record_size = self._parse_ownership_header(data)
                if launch_id:
                    records.append(launch_id)
                    if launch_id2 != launch_id:
                        records.append(launch_id2)
                    global_offset += record_size
                else:
                    break
        except:
            log.exception("parse_ownership failed with exception. Possibly 'ownership' file corrupted")
            return []
        return records

    def _parse_user_settings(self):
        def get_game_id(data, rec_size):
            i = 0
            multiplier = 1
            game_id = 0
            while i < rec_size:
                game_id += data[i] * multiplier
                multiplier *= 256
                i += 1

            if game_id > 256 * 256:
                game_id -= (128 * 256 * math.ceil(game_id / (256 * 256)))
                game_id -= (128 * math.ceil(game_id / 256))
            else:
                if game_id > 256:
                    game_id -= (128 * math.ceil(game_id / 256))

            return str(game_id)
        """
            0Ah - file start
            0Ah - hidden games records
                00h -> no hidden games
                !00h -> hidden games (hidden games total entry size)
                    0Ah - SEPARATOR
                    03h - RECORD SIZE
                    08h - SEPARATOR
                    [RECORD_SIZE-1] -> game_ID in konrad's format
                    [..]
            12h -> fav games records
                00h -> no fav games
                !00h -> fav games (fav games total entry size)
                    0Ah - SEPARATOR
                    03h - RECORD SIZE
                    08h - SEPARATOR
                    [RECORD_SIZE-1] -> game_ID in konrad's format
                    [..]
        """
        global_offset = 1
        fav = set()
        hidden = set()
        data = self.settings_raw
        if data[global_offset] != 0:
            buffer = int(data[global_offset])
            fav_records = data[global_offset + 1:global_offset + buffer + 1]
        else:
            fav_records = []

        global_offset = len(fav_records) + 3
        if data[global_offset] != 0:
            buffer = int(data[global_offset])
            hidden_records = data[global_offset + 1:global_offset + buffer + 1]
        else:
            hidden_records = []

        pos = 0
        while pos < len(fav_records):
            rec_size = fav_records[pos + 1] - 1
            rec_data = fav_records[pos + 3:pos + 3 + rec_size]
            fav.add(get_game_id(rec_data, rec_size))
            pos += rec_size + 3

        pos = 0
        while pos < len(hidden_records):
            rec_size = hidden_records[pos + 1] - 1
            rec_data = hidden_records[pos + 3:pos + 3 + rec_size]
            hidden.add(get_game_id(rec_data, rec_size))
            pos += rec_size + 3

        return fav, hidden

    def _get_field_from_yaml(self, game_yaml, field="name"):
        field_value = ''

        if field in game_yaml['root']:
            field_value = game_yaml['root'][field]
        # Fallback 1
        if field == "name" and field_value.lower() in UBISOFT_CONFIGURATIONS_BLACKLISTED_NAMES:
            if 'installer' in game_yaml['root'] and 'game_identifier' in game_yaml['root']['installer']:
                field_value = game_yaml['root']['installer']['game_identifier']
        # Fallback 2
        if field_value.lower() in UBISOFT_CONFIGURATIONS_BLACKLISTED_NAMES:
            if 'localizations' in game_yaml and 'default' in game_yaml['localizations'] and field_value in \
                    game_yaml['localizations']['default']:
                field_value = game_yaml['localizations']['default'][field_value]
        return field_value

    def _get_steam_game_properties_from_yaml(self, game_yaml):
        path = ''
        third_party_id = ''
        if 'third_party_steam' in game_yaml['root']['start_game']:
            path = game_yaml['root']['start_game']['third_party_steam']['game_installation_status_register']
            third_party_id = game_yaml['root']['start_game']['third_party_steam']['steam_app_id']
        elif 'steam' in game_yaml['root']['start_game']:
            path = game_yaml['root']['start_game']['steam']['game_installation_status_register']
            third_party_id = game_yaml['root']['start_game']['steam']['steam_app_id']
        return path, third_party_id

    def _get_registry_properties_from_yaml(self, game_yaml):
        game_registry_path = ''
        exe = ''
        registry_path = game_yaml['root']['start_game']['online']['executables'][0]['working_directory']['register']
        game_registry_path = registry_path
        try:
            exe = game_yaml['root']['start_game']['online']['executables'][0]['path']['relative']
        except KeyError:
            exe = game_yaml['root']['start_game']['online']['executables'][0]['path']['register']
        return game_registry_path, exe

    def _parse_game(self, game_yaml, install_id, launch_id):
        space_id = ''
        launch_id = str(launch_id)
        install_id = str(install_id)
        if 'space_id' in game_yaml['root']:
            space_id = game_yaml['root']['space_id']
        game_name = self._get_field_from_yaml(game_yaml, "name")
        thumb_image = self._get_field_from_yaml(game_yaml, "thumb_image")
        registry_path, exe = self._get_registry_properties_from_yaml(game_yaml)
        return {
            "spaceId": space_id,
            "launchId": launch_id,
            "installId": install_id,
            "name": game_name,
            "thumbImage": thumb_image,
            "registryPath": registry_path,
            "exe": exe
        }

    def _iter_configuration_items(self):
        configuration_records = self._parse_configuration()
        for _, game in configuration_records.items():
            if game["size"]:
                yield game

    def _parse_configuration_item(self, conf_item):
        stream = self.configuration_raw[
            conf_item['offset']: conf_item['offset'] + conf_item['size']
        ].decode("utf8", errors='ignore')
        if stream and 'start_game' in stream:
            return yaml.load(stream.replace('\t', ' '), Loader=yaml.FullLoader)

    def parse_games(self, configuration_data):
        self.configuration_raw = configuration_data
        for game in self._iter_configuration_items():
            yaml_object = self._parse_configuration_item(game)
            if yaml_object:
                yield self._parse_game(yaml_object, game['install_id'], game['launch_id'])

    def get_owned_local_games(self, ownership_data):
        self.ownership_raw = ownership_data
        return self._parse_ownership()

    def get_game_tags(self, settings_data):
        self.settings_raw = settings_data
        return self._parse_user_settings()
