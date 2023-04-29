import struct
from io import BytesIO

# for the record:
#  - int32 = signed varint
#  - int64 = signed varint
#  - enum = signed varint
#  - uint32 = unsigned varint
#  - uint64 = unsigned varint
#  - sint32 = zigzag signed varint
#  - sint64 = zigzag signed varint

# https://developers.google.com/protocol-buffers/docs/encoding
# 0  Varint             int32, int64, uint32, uint64, sint32, sint64, bool, enum
# 1  64-bit             fixed64, sfixed64, double
# 2  Length-delimited   string, bytes, embedded messages, packed repeated fields
# 3  Start group        groups (deprecated)
# 4  End group	        groups (deprecated)
# 5  32-bit             fixed32, sfixed32, float


class PrimativeType:
    @staticmethod
    def decode(data):
        raise NotImplementedError()


class type_double(PrimativeType):
    wire_type = 1

    @staticmethod
    def decode(data):
        # data = 64-bit
        val, = struct.unpack("<d", data)
        return val


class type_float(PrimativeType):
    wire_type = 5

    @staticmethod
    def decode(data):
        # data = 32-bit
        val, = struct.unpack("<f", data)
        return val


class type_int32(PrimativeType):
    wire_type = 0

    @staticmethod
    def decode(data):
        # data = signed varint
        val = Message.signed_to_long(data, 32)
        return int(val)


class type_int64(PrimativeType):
    wire_type = 0

    @staticmethod
    def decode(data):
        # data = signed varint
        val = Message.signed_to_long(data, 64)
        return int(val)


class type_uint32(PrimativeType):
    wire_type = 0

    @staticmethod
    def decode(data):
        # data = unsigned varint
        return int(data)


class type_uint64(PrimativeType):
    wire_type = 0

    @staticmethod
    def decode(data):
        # data = unsigned varint
        return int(data)


class type_sint32(PrimativeType):
    wire_type = 0

    @staticmethod
    def decode(data):
        # data = zigzag signed varint
        val = Message.signed_to_long(data, 32)
        val = Message.zigzag_to_long(val)
        return int(val)


class type_sint64(PrimativeType):
    wire_type = 0

    @staticmethod
    def decode(data):
        # data = zigzag signed varint
        val = Message.signed_to_long(data, 64)
        val = Message.zigzag_to_long(val)
        return int(val)


class type_fixed32(PrimativeType):
    wire_type = 5

    @staticmethod
    def decode(data):
        # data = 32-bit
        val, = struct.unpack("<I", data)
        return int(val)


class type_fixed64(PrimativeType):
    wire_type = 1

    @staticmethod
    def decode(data):
        # data = 64-bit
        val, = struct.unpack("<Q", data)
        return int(val)


class type_sfixed32(PrimativeType):
    wire_type = 5

    @staticmethod
    def decode(data):
        # data = 32-bit
        val, = struct.unpack("<i", data)
        return int(val)


class type_sfixed64(PrimativeType):
    wire_type = 1

    @staticmethod
    def decode(data):
        # data = 64-bit
        val, = struct.unpack("<q", data)
        return int(val)


class type_bool(PrimativeType):
    wire_type = 0

    @staticmethod
    def decode(data):
        # data = signed varint
        return data != 0


class type_string(PrimativeType):
    wire_type = 2

    @staticmethod
    def decode(data):
        # data = binary string
        return data


class type_bytes(PrimativeType):
    wire_type = 2

    @staticmethod
    def decode(data):
        # data = binary string
        return data


# probs best to go with int64
type_enum = type_int64


class Message:
    @staticmethod
    def read_varint(stream):
        res = 0
        i = 0
        while 1:
            c = ord(stream.read(1))
            res |= ((c & 127) << (i * 7))
            if c & 128 == 0:
                break
            i += 1
        return res

    @staticmethod
    def signed_to_long(x, bits):
        " converts a previously read signed varint into a long "
        if x > 0x7fffffffffffffff:
            x -= (1 << 64)
            x |= ~((1 << bits) - 1)
        else:
            x &= (1 << bits) - 1
        return x

    # zigzag conversion from google
    # https://github.com/google/protobuf/blob/master/python/google/protobuf/internal/wire_format.py

    @staticmethod
    def zigzag_to_long(x):
        if not x & 0x1:
            return x >> 1
        return (x >> 1) ^ (~0)

    @staticmethod
    def read_tag(stream):
        var = Message.read_varint(stream)
        field_number = var >> 3
        wire_type = var & 7

        if wire_type == 0:
            data = Message.read_varint(stream)
        elif wire_type == 1:
            data = stream.read(8)
        elif wire_type == 2:
            length = Message.read_varint(stream)
            data = stream.read(length)
        elif wire_type in (3, 4):
            raise NotImplementedError("groups are deprecated")
        elif wire_type == 5:
            data = stream.read(4)
        else:
            raise TypeError("unknown wire type (%d)" % wire_type)
        return (field_number, wire_type, data)

    def lookup_id(self, _id):
        for _, i in enumerate(self.__lookup__):
            if i[3] == _id:
                return i

    def decode(self, s: bytes):

        f = BytesIO(s)
        while f.tell() < len(s):
            field_number, _, data = self.read_tag(f)
            field = self.lookup_id(field_number)
            if not field:
                continue

            field_multiplicity, field_type, field_name, _ = field
            if issubclass(field_type, PrimativeType):
                value = field_type.decode(data)
            elif issubclass(field_type, Message):
                value = field_type()
                value.decode(data)
            else:
                raise TypeError("field type must be a subclass of PrimativeType or Message")

            if field_multiplicity == "repeated":
                if getattr(self, field_name) is None:
                    # if not isinstance(getattr(self, field_name), list):
                    # ? what if the attribute was already filled with data ?
                    setattr(self, field_name, [])
                getattr(self, field_name).append(value)
            else:
                setattr(self, field_name, value)

    def __lookup__(self):
        return
