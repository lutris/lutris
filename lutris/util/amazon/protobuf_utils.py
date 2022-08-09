import struct
from io import BytesIO, StringIO

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

    @staticmethod
    def encode(value):
        assert isinstance(value, float)
        return struct.pack("<d", value)


class type_float(PrimativeType):
    wire_type = 5

    @staticmethod
    def decode(data):
        # data = 32-bit
        val, = struct.unpack("<f", data)
        return val

    @staticmethod
    def encode(value):
        assert isinstance(value, float)
        return struct.pack("<f", value)


class type_int32(PrimativeType):
    wire_type = 0

    @staticmethod
    def decode(data):
        # data = signed varint
        val = Message.signed_to_long(data, 32)
        return int(val)

    @staticmethod
    def encode(value):
        assert isinstance(value, int)
        val = Message.long_to_signed(value)
        return val


class type_int64(PrimativeType):
    wire_type = 0

    @staticmethod
    def decode(data):
        # data = signed varint
        val = Message.signed_to_long(data, 64)
        return int(val)

    @staticmethod
    def encode(value):
        assert isinstance(value, int)
        val = Message.long_to_signed(value)
        return val


class type_uint32(PrimativeType):
    wire_type = 0

    @staticmethod
    def decode(data):
        # data = unsigned varint
        return int(data)

    @staticmethod
    def encode(value):
        assert isinstance(value, int)
        return value


class type_uint64(PrimativeType):
    wire_type = 0

    @staticmethod
    def decode(data):
        # data = unsigned varint
        return int(data)

    @staticmethod
    def encode(value):
        assert isinstance(value, int)
        return value


class type_sint32(PrimativeType):
    wire_type = 0

    @staticmethod
    def decode(data):
        # data = zigzag signed varint
        val = Message.signed_to_long(data, 32)
        val = Message.zigzag_to_long(val)
        return int(val)

    @staticmethod
    def encode(value):
        assert isinstance(value, int)
        val = Message.long_to_zigzag(value)
        val = Message.long_to_signed(val)
        return val


class type_sint64(PrimativeType):
    wire_type = 0

    @staticmethod
    def decode(data):
        # data = zigzag signed varint
        val = Message.signed_to_long(data, 64)
        val = Message.zigzag_to_long(val)
        return int(val)

    @staticmethod
    def encode(value):
        assert isinstance(value, int)
        val = Message.long_to_zigzag(value)
        val = Message.long_to_signed(val)
        return val


class type_fixed32(PrimativeType):
    wire_type = 5

    @staticmethod
    def decode(data):
        # data = 32-bit
        val, = struct.unpack("<I", data)
        return int(val)

    @staticmethod
    def encode(value):
        assert isinstance(value, int)
        return struct.pack("<I", value)


class type_fixed64(PrimativeType):
    wire_type = 1

    @staticmethod
    def decode(data):
        # data = 64-bit
        val, = struct.unpack("<Q", data)
        return int(val)

    @staticmethod
    def encode(value):
        assert isinstance(value, int)
        return struct.pack("<Q", value)


class type_sfixed32(PrimativeType):
    wire_type = 5

    @staticmethod
    def decode(data):
        # data = 32-bit
        val, = struct.unpack("<i", data)
        return int(val)

    @staticmethod
    def encode(value):
        assert isinstance(value, int)
        return struct.pack("<i", value)


class type_sfixed64(PrimativeType):
    wire_type = 1

    @staticmethod
    def decode(data):
        # data = 64-bit
        val, = struct.unpack("<q", data)
        return int(val)

    @staticmethod
    def encode(value):
        assert isinstance(value, int)
        return struct.pack("<q", value)


class type_bool(PrimativeType):
    wire_type = 0

    @staticmethod
    def decode(data):
        # data = signed varint
        return data != 0

    @staticmethod
    def encode(value):
        assert isinstance(value, bool)
        return int(value)


class type_string(PrimativeType):
    wire_type = 2

    @staticmethod
    def decode(data):
        # data = binary string
        return data

    @staticmethod
    def encode(value):
        assert isinstance(value, str)
        return value


class type_bytes(PrimativeType):
    wire_type = 2

    @staticmethod
    def decode(data):
        # data = binary string
        return data

    @staticmethod
    def encode(value):
        assert isinstance(value, str)
        return value


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
    def write_varint(stream, x):
        if x < 0:
            raise TypeError("unsigned values only")
        while 1:
            if x > 127:
                stream.write(chr((1 << 7) | (x & 0x7F)))
                x >>= 7
            else:
                stream.write(chr(x))
                break

    @staticmethod
    def signed_to_long(x, bits):
        " converts a previously read signed varint into a long "
        if x > 0x7fffffffffffffff:
            x -= (1 << 64)
            x |= ~((1 << bits) - 1)
        else:
            x &= (1 << bits) - 1
        return x

    @staticmethod
    def long_to_signed(x):
        " converts a long into a format for writing as a signed varint "
        if x < 0:
            # as is in google's protobuf
            # https://github.com/google/protobuf/blob/master/python/google/protobuf/internal/encoder.py
            x += (1 << 64)
        return x

    # zigzag conversion from google
    # https://github.com/google/protobuf/blob/master/python/google/protobuf/internal/wire_format.py

    @staticmethod
    def long_to_zigzag(x):
        if x >= 0:
            return x << 1
        return (x << 1) ^ (~0)

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
            raise Exception("unknown wire type (%d)" % wire_type)
        return (field_number, wire_type, data)

    @staticmethod
    def write_tag(stream, field_number, wire_type, data):
        tag = (field_number << 3) | (wire_type & 7)
        Message.write_varint(stream, tag)

        if wire_type == 0:
            Message.write_varint(stream, data)
        elif wire_type == 1:
            assert len(data) == 8
            stream.write(data)
        elif wire_type == 2:
            Message.write_varint(stream, len(data))
            stream.write(data)
        elif wire_type in (3, 4):
            raise NotImplementedError("groups are deprecated")
        elif wire_type == 5:
            assert len(data) == 4
            stream.write(data)
        else:
            raise Exception("unknown wire type (%d)" % wire_type)

    def lookup_id(self, _id):
        for _, i in enumerate(self.__lookup__):
            if i[3] == _id:
                return i

    def lookup_name(self, _name):
        for _, i in enumerate(self.__lookup__):
            if i[2] == _name:
                return i

    def decode(self, s):

        if isinstance(s, str):
            f = StringIO(s)
        elif isinstance(s, bytes):
            f = BytesIO(s)
        else:
            return

        length = len(s)
        while f.tell() < length:
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
                raise Exception("field type must be a subclass of PrimativeType or Message")

            if field_multiplicity == "repeated":
                if getattr(self, field_name) is None:
                    # if not isinstance(getattr(self, field_name), list):
                    # ? what if the attribute was already filled with data ?
                    setattr(self, field_name, [])
                getattr(self, field_name).append(value)
            else:
                setattr(self, field_name, value)

    def encode(self):
        buf = StringIO()
        for field_multiplicity, field_type, field_name, field_number in self.__lookup__:
            data = getattr(self, field_name)
            if data is None:
                # FIX: remove string comparisions
                if field_multiplicity == "required":
                    raise Exception("field (%s) is required but has not been set" % field_name)
                continue

            def encode_value(value):
                if issubclass(field_type, PrimativeType):
                    data = field_type.encode(value)
                    wire_type = field_type.wire_type
                elif issubclass(field_type, Message):
                    data = value.encode()
                    wire_type = 2
                else:
                    raise Exception("field type must be a subclass of PrimativeType or Message")
                return (data, wire_type)

            if field_multiplicity == "repeated":
                for item in data:
                    data, wire_type = encode_value(item)
                    Message.write_tag(buf, field_number, wire_type, data)
            else:
                data, wire_type = encode_value(data)
                Message.write_tag(buf, field_number, wire_type, data)

        return buf.getvalue()

    @classmethod
    def from_dict(cls, dictionary):
        self = cls()
        for field_multiplicity, field_type, field_name, _ in self.__lookup__:
            if field_name not in dictionary:
                continue

            def decode_value(value):
                if issubclass(field_type, Message):
                    value = field_type.from_dict(value)
                return value

            data = dictionary[field_name]
            if field_multiplicity == "repeated":
                setattr(self, field_name, [decode_value(item) for item in data])
            else:
                setattr(self, field_name, decode_value(data))

        return self

    def to_dict(self):
        # dict-ify
        res = {}
        for field_multiplicity, field_type, field_name, _ in self.__lookup__:
            data = getattr(self, field_name)
            if data is None:
                continue

            def encode_value(value):
                if issubclass(field_type, Message):
                    value = value.to_dict()
                return value

            if field_multiplicity == "repeated":
                res[field_name] = [encode_value(item) for item in data]
            else:
                res[field_name] = encode_value(data)

        return res

    def __repr__(self):
        return str(self.to_dict())

    def __lookup__(self):
        return


def debug_binary_protobuf(data, depth=1):
    s = StringIO(data)
    length = len(data)
    while s.tell() < length:
        field_number, wire_type, data = Message.read_tag(s)
        print("-" * (depth * 3), "field:", field_number, "wire type:", wire_type, "data:", repr(data))
        if wire_type == 2:
            try:
                debug_binary_protobuf(data, depth + 1)
            except:
                print("-" * ((depth + 1) * 3), "failed to decode inside")
