from lutris.util.amazon.protobuf_decoder import (
    Message, type_bool, type_bytes, type_enum, type_int64, type_string, type_uint32
)


class CompressionAlgorithm:
    none = 0
    lzma = 1


class HashAlgorithm:
    sha256 = 0
    shake128 = 1

    @staticmethod
    def get_name(algorithm):
        if algorithm == HashAlgorithm.sha256:
            return "SHA256"

        if algorithm == HashAlgorithm.shake128:
            return "SHAKE128"

        return None


class SignatureAlgorithm:
    sha256_with_rsa = 0


class CompressionSettings(Message):
    algorithm = CompressionAlgorithm.none

    def __init__(self):
        self.__lookup__ = [("optional", type_enum, "algorithm", 1)]


class Dir(Message):
    path = None
    mode = None

    def __init__(self):
        self.__lookup__ = [("optional", type_string, "path", 1),
                           ("optional", type_uint32, "mode", 2)]


class File(Message):
    path = None
    mode = None
    size = None
    created = None
    hash = None
    hidden = None
    system = None

    def __init__(self):
        self.__lookup__ = [("optional", type_string, "path", 1),
                           ("optional", type_uint32, "mode", 2),
                           ("optional", type_int64, "size", 3),
                           ("optional", type_string, "created", 4),
                           ("optional", Hash, "hash", 5),
                           ("optional", type_bool, "hidden", 6),
                           ("optional", type_bool, "system", 7)]


class Hash(Message):
    algorithm = HashAlgorithm.sha256
    value = None

    def __init__(self):
        self.__lookup__ = [("optional", type_enum, "algorithm", 1),
                           ("optional", type_bytes, "value", 2)]


class Manifest(Message):
    packages = None

    def __init__(self):
        self.__lookup__ = [("repeated", Package, "packages", 1)]


class ManifestHeader(Message):
    compression = None
    hash = None
    signature = None

    def __init__(self):
        self.__lookup__ = [("optional", CompressionSettings, "compression", 1),
                           ("optional", Hash, "hash", 2),
                           ("optional", Signature, "signature", 3)]


class Package(Message):
    name = None
    files = None
    dirs = None

    def __init__(self):
        self.__lookup__ = [("optional", type_string, "name", 1),
                           ("repeated", File, "files", 2),
                           ("repeated", Dir, "dirs", 3)]


class Signature(Message):
    algorithm = SignatureAlgorithm.sha256_with_rsa
    value = None

    def __init__(self):
        self.__lookup__ = [("optional", type_enum, "algorithm", 1),
                           ("optional", type_bytes, "value", 2)]
