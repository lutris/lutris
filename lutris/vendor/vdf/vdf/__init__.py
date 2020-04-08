"""
Module for deserializing/serializing to and from VDF
"""
__version__ = "3.2"
__author__ = "Rossen Georgiev"

import re
import sys
import struct
from binascii import crc32
from io import StringIO as unicodeIO
from vdf.vdict import VDFDict

# Py2 & Py3 compatibility
if sys.version_info[0] >= 3:
    string_type = str
    int_type = int
    BOMS = '\ufffe\ufeff'

    def strip_bom(line):
        return line.lstrip(BOMS)
else:
    from StringIO import StringIO as strIO
    string_type = basestring
    int_type = long
    BOMS = '\xef\xbb\xbf\xff\xfe\xfe\xff'
    BOMS_UNICODE = '\\ufffe\\ufeff'.decode('unicode-escape')

    def strip_bom(line):
        return line.lstrip(BOMS if isinstance(line, str) else BOMS_UNICODE)

# string escaping
_unescape_char_map = {
    r"\n": "\n",
    r"\t": "\t",
    r"\v": "\v",
    r"\b": "\b",
    r"\r": "\r",
    r"\f": "\f",
    r"\a": "\a",
    r"\\": "\\",
    r"\?": "?",
    r"\"": "\"",
    r"\'": "\'",
}
_escape_char_map = {v: k for k, v in _unescape_char_map.items()}

def _re_escape_match(m):
    return _escape_char_map[m.group()]

def _re_unescape_match(m):
    return _unescape_char_map[m.group()]

def _escape(text):
    return re.sub(r"[\n\t\v\b\r\f\a\\\?\"']", _re_escape_match, text)

def _unescape(text):
    return re.sub(r"(\\n|\\t|\\v|\\b|\\r|\\f|\\a|\\\\|\\\?|\\\"|\\')", _re_unescape_match, text)

# parsing and dumping for KV1
def parse(fp, mapper=dict, merge_duplicate_keys=True, escaped=True):
    """
    Deserialize ``s`` (a ``str`` or ``unicode`` instance containing a VDF)
    to a Python object.

    ``mapper`` specifies the Python object used after deserializetion. ``dict` is
    used by default. Alternatively, ``collections.OrderedDict`` can be used if you
    wish to preserve key order. Or any object that acts like a ``dict``.

    ``merge_duplicate_keys`` when ``True`` will merge multiple KeyValue lists with the
    same key into one instead of overwriting. You can se this to ``False`` if you are
    using ``VDFDict`` and need to preserve the duplicates.
    """
    if not issubclass(mapper, dict):
        raise TypeError("Expected mapper to be subclass of dict, got %s" % type(mapper))
    if not hasattr(fp, 'readline'):
        raise TypeError("Expected fp to be a file-like object supporting line iteration")

    stack = [mapper()]
    expect_bracket = False

    re_keyvalue = re.compile(r'^("(?P<qkey>(?:\\.|[^\\"])+)"|(?P<key>#?[a-z0-9\-\_\\\?]+))'
                             r'([ \t]*('
                             r'"(?P<qval>(?:\\.|[^\\"])*)(?P<vq_end>")?'
                             r'|(?P<val>[a-z0-9\-\_\\\?\*\.]+)'
                             r'))?',
                             flags=re.I)

    for lineno, line in enumerate(fp, 1):
        if lineno == 1:
            line = strip_bom(line)

        line = line.lstrip()

        # skip empty and comment lines
        if line == "" or line[0] == '/':
            continue

        # one level deeper
        if line[0] == "{":
            expect_bracket = False
            continue

        if expect_bracket:
            raise SyntaxError("vdf.parse: expected openning bracket",
                              (getattr(fp, 'name', '<%s>' % fp.__class__.__name__), lineno, 1, line))

        # one level back
        if line[0] == "}":
            if len(stack) > 1:
                stack.pop()
                continue

            raise SyntaxError("vdf.parse: one too many closing parenthasis",
                              (getattr(fp, 'name', '<%s>' % fp.__class__.__name__), lineno, 0, line))

        # parse keyvalue pairs
        while True:
            match = re_keyvalue.match(line)

            if not match:
                try:
                    line += next(fp)
                    continue
                except StopIteration:
                    raise SyntaxError("vdf.parse: unexpected EOF (open key quote?)",
                                      (getattr(fp, 'name', '<%s>' % fp.__class__.__name__), lineno, 0, line))

            key = match.group('key') if match.group('qkey') is None else match.group('qkey')
            val = match.group('val') if match.group('qval') is None else match.group('qval')

            if escaped:
                key = _unescape(key)

            # we have a key with value in parenthesis, so we make a new dict obj (level deeper)
            if val is None:
                if merge_duplicate_keys and key in stack[-1]:
                    _m = stack[-1][key]
                else:
                    _m = mapper()
                    stack[-1][key] = _m

                stack.append(_m)
                expect_bracket = True

            # we've matched a simple keyvalue pair, map it to the last dict obj in the stack
            else:
                # if the value is line consume one more line and try to match again,
                # until we get the KeyValue pair
                if match.group('vq_end') is None and match.group('qval') is not None:
                    try:
                        line += next(fp)
                        continue
                    except StopIteration:
                        raise SyntaxError("vdf.parse: unexpected EOF (open quote for value?)",
                                          (getattr(fp, 'name', '<%s>' % fp.__class__.__name__), lineno, 0, line))

                stack[-1][key] = _unescape(val) if escaped else val

            # exit the loop
            break

    if len(stack) != 1:
        raise SyntaxError("vdf.parse: unclosed parenthasis or quotes (EOF)",
                           (getattr(fp, 'name', '<%s>' % fp.__class__.__name__), lineno, 0, line))

    return stack.pop()


def loads(s, **kwargs):
    """
    Deserialize ``s`` (a ``str`` or ``unicode`` instance containing a JSON
    document) to a Python object.
    """
    if not isinstance(s, string_type):
        raise TypeError("Expected s to be a str, got %s" % type(s))

    try:
        fp = unicodeIO(s)
    except TypeError:
        fp = strIO(s)

    return parse(fp, **kwargs)


def load(fp, **kwargs):
    """
    Deserialize ``fp`` (a ``.readline()``-supporting file-like object containing
    a JSON document) to a Python object.
    """
    return parse(fp, **kwargs)


def dumps(obj, pretty=False, escaped=True):
    """
    Serialize ``obj`` to a VDF formatted ``str``.
    """
    if not isinstance(obj, dict):
        raise TypeError("Expected data to be an instance of``dict``")
    if not isinstance(pretty, bool):
        raise TypeError("Expected pretty to be of type bool")
    if not isinstance(escaped, bool):
        raise TypeError("Expected escaped to be of type bool")

    return ''.join(_dump_gen(obj, pretty, escaped))


def dump(obj, fp, pretty=False, escaped=True):
    """
    Serialize ``obj`` as a VDF formatted stream to ``fp`` (a
    ``.write()``-supporting file-like object).
    """
    if not isinstance(obj, dict):
        raise TypeError("Expected data to be an instance of``dict``")
    if not hasattr(fp, 'write'):
        raise TypeError("Expected fp to have write() method")
    if not isinstance(pretty, bool):
        raise TypeError("Expected pretty to be of type bool")
    if not isinstance(escaped, bool):
        raise TypeError("Expected escaped to be of type bool")

    for chunk in _dump_gen(obj, pretty, escaped):
        fp.write(chunk)


def _dump_gen(data, pretty=False, escaped=True, level=0):
    indent = "\t"
    line_indent = ""

    if pretty:
        line_indent = indent * level

    for key, value in data.items():
        if escaped and isinstance(key, string_type):
            key = _escape(key)

        if isinstance(value, dict):
            yield '%s"%s"\n%s{\n' % (line_indent, key, line_indent)
            for chunk in _dump_gen(value, pretty, escaped, level+1):
                yield chunk
            yield "%s}\n" % line_indent
        else:
            if escaped and isinstance(value, string_type):
                value = _escape(value)

            yield '%s"%s" "%s"\n' % (line_indent, key, value)


# binary VDF
class BASE_INT(int_type):
    def __repr__(self):
        return "%s(%d)" % (self.__class__.__name__, self)

class UINT_64(BASE_INT):
    pass

class INT_64(BASE_INT):
    pass

class POINTER(BASE_INT):
    pass

class COLOR(BASE_INT):
    pass

BIN_NONE        = b'\x00'
BIN_STRING      = b'\x01'
BIN_INT32       = b'\x02'
BIN_FLOAT32     = b'\x03'
BIN_POINTER     = b'\x04'
BIN_WIDESTRING  = b'\x05'
BIN_COLOR       = b'\x06'
BIN_UINT64      = b'\x07'
BIN_END         = b'\x08'
BIN_INT64       = b'\x0A'
BIN_END_ALT     = b'\x0B'

def binary_loads(s, mapper=dict, merge_duplicate_keys=True, alt_format=False):
    """
    Deserialize ``s`` (``bytes`` containing a VDF in "binary form")
    to a Python object.

    ``mapper`` specifies the Python object used after deserializetion. ``dict` is
    used by default. Alternatively, ``collections.OrderedDict`` can be used if you
    wish to preserve key order. Or any object that acts like a ``dict``.

    ``merge_duplicate_keys`` when ``True`` will merge multiple KeyValue lists with the
    same key into one instead of overwriting. You can se this to ``False`` if you are
    using ``VDFDict`` and need to preserve the duplicates.
    """
    if not isinstance(s, bytes):
        raise TypeError("Expected s to be bytes, got %s" % type(s))
    if not issubclass(mapper, dict):
        raise TypeError("Expected mapper to be subclass of dict, got %s" % type(mapper))

    # helpers
    int32 = struct.Struct('<i')
    uint64 = struct.Struct('<Q')
    int64 = struct.Struct('<q')
    float32 = struct.Struct('<f')

    def read_string(s, idx, wide=False):
        if wide:
            end = s.find(b'\x00\x00', idx)
            if (end - idx) % 2 != 0:
                end += 1
        else:
            end = s.find(b'\x00', idx)

        if end == -1:
            raise SyntaxError("Unterminated cstring (offset: %d)" % idx)
        result = s[idx:end]
        if wide:
            result = result.decode('utf-16')
        elif bytes is not str:
            result = result.decode('utf-8', 'replace')
        else:
            try:
                result.decode('ascii')
            except:
                result = result.decode('utf-8', 'replace')
        return result, end + (2 if wide else 1)

    stack = [mapper()]
    idx = 0
    CURRENT_BIN_END = BIN_END if not alt_format else BIN_END_ALT

    while len(s) > idx:
        t = s[idx:idx+1]
        idx += 1

        if t == CURRENT_BIN_END:
            if len(stack) > 1:
                stack.pop()
                continue
            break

        key, idx = read_string(s, idx)

        if t == BIN_NONE:
            if merge_duplicate_keys and key in stack[-1]:
                _m = stack[-1][key]
            else:
                _m = mapper()
                stack[-1][key] = _m
            stack.append(_m)
        elif t == BIN_STRING:
            stack[-1][key], idx = read_string(s, idx)
        elif t == BIN_WIDESTRING:
            stack[-1][key], idx = read_string(s, idx, wide=True)
        elif t in (BIN_INT32, BIN_POINTER, BIN_COLOR):
            val = int32.unpack_from(s, idx)[0]

            if t == BIN_POINTER:
                val = POINTER(val)
            elif t == BIN_COLOR:
                val = COLOR(val)

            stack[-1][key] = val
            idx += int32.size
        elif t == BIN_UINT64:
            stack[-1][key] = UINT_64(uint64.unpack_from(s, idx)[0])
            idx += uint64.size
        elif t == BIN_INT64:
            stack[-1][key] = INT_64(int64.unpack_from(s, idx)[0])
            idx += int64.size
        elif t == BIN_FLOAT32:
            stack[-1][key] = float32.unpack_from(s, idx)[0]
            idx += float32.size
        else:
            raise SyntaxError("Unknown data type at offset %d: %s" % (idx-1, repr(t)))

    if len(s) != idx or len(stack) != 1:
        raise SyntaxError("Binary VDF ended at offset %d, but length is %d" % (idx, len(s)))

    return stack.pop()

def binary_dumps(obj, alt_format=False):
    """
    Serialize ``obj`` to a binary VDF formatted ``bytes``.
    """
    return b''.join(_binary_dump_gen(obj, alt_format=alt_format))

def _binary_dump_gen(obj, level=0, alt_format=False):
    if level == 0 and len(obj) == 0:
        return

    int32 = struct.Struct('<i')
    uint64 = struct.Struct('<Q')
    int64 = struct.Struct('<q')
    float32 = struct.Struct('<f')

    for key, value in obj.items():
        if isinstance(key, string_type):
            key = key.encode('utf-8')
        else:
            raise TypeError("dict keys must be of type str, got %s" % type(key))

        if isinstance(value, dict):
            yield BIN_NONE + key + BIN_NONE
            for chunk in _binary_dump_gen(value, level+1, alt_format=alt_format):
                yield chunk
        elif isinstance(value, UINT_64):
            yield BIN_UINT64 + key + BIN_NONE + uint64.pack(value)
        elif isinstance(value, INT_64):
            yield BIN_INT64 + key + BIN_NONE + int64.pack(value)
        elif isinstance(value, string_type):
            try:
                value = value.encode('utf-8') + BIN_NONE
                yield BIN_STRING
            except:
                value = value.encode('utf-16') + BIN_NONE*2
                yield BIN_WIDESTRING
            yield key + BIN_NONE + value
        elif isinstance(value, float):
            yield BIN_FLOAT32 + key + BIN_NONE + float32.pack(value)
        elif isinstance(value, (COLOR, POINTER, int, int_type)):
            if isinstance(value, COLOR):
                yield BIN_COLOR
            elif isinstance(value, POINTER):
                yield BIN_POINTER
            else:
                yield BIN_INT32
            yield key + BIN_NONE
            yield int32.pack(value)
        else:
            raise TypeError("Unsupported type: %s" % type(value))

    yield BIN_END if not alt_format else BIN_END_ALT


def vbkv_loads(s, mapper=dict, merge_duplicate_keys=True):
    """
    Deserialize ``s`` (``bytes`` containing a VBKV to a Python object.

    ``mapper`` specifies the Python object used after deserializetion. ``dict` is
    used by default. Alternatively, ``collections.OrderedDict`` can be used if you
    wish to preserve key order. Or any object that acts like a ``dict``.

    ``merge_duplicate_keys`` when ``True`` will merge multiple KeyValue lists with the
    same key into one instead of overwriting. You can se this to ``False`` if you are
    using ``VDFDict`` and need to preserve the duplicates.
    """
    if s[:4] != b'VBKV':
        raise ValueError("Invalid header")

    checksum, = struct.unpack('<i', s[4:8])

    if checksum != crc32(s[8:]):
        raise ValueError("Invalid checksum")

    return binary_loads(s[8:], mapper, merge_duplicate_keys, alt_format=True)

def vbkv_dumps(obj):
    """
    Serialize ``obj`` to a VBKV formatted ``bytes``.
    """
    data =  b''.join(_binary_dump_gen(obj, alt_format=True))
    checksum = crc32(data)

    return b'VBKV' + struct.pack('<i', checksum) + data
