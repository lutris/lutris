from lutris.util import system


class RetroConfig:
    value_map = {"true": True, "false": False, "": None}

    def __init__(self, config_path):
        if not config_path:
            raise ValueError("Config path is mandatory")
        if not system.path_exists(config_path):
            raise OSError("Specified config file {} does not exist".format(config_path))
        self.config_path = config_path
        self.config = []
        with open(config_path, "r") as config_file:
            for line in config_file.readlines():
                if not line:
                    continue
                line = line.strip()
                if line == "" or line.startswith('#'):
                    continue
                key, value = line.split("=")
                key = key.strip()
                value = value.strip().strip('"')
                if not key or not value:
                    continue
                self.config.append((key, value))

    def save(self):
        with open(self.config_path, "w") as config_file:
            for (key, value) in self.config:
                config_file.write('{} = "{}"\n'.format(key, value))

    def serialize_value(self, value):
        for k, v in self.value_map.items():
            if value is v:
                return k
        return value

    def deserialize_value(self, value):
        for k, v in self.value_map.items():
            if value == k:
                return v
        return value

    def __getitem__(self, key):
        for k, value in self.config:
            if key == k:
                return self.deserialize_value(value)

    def __setitem__(self, key, value):
        for index, conf in enumerate(self.config):
            if key == conf[0]:
                self.config[index] = (key, self.serialize_value(value))
                return
        self.config.append((key, self.serialize_value(value)))

    def keys(self):
        return list([key for (key, _value) in self.config])
