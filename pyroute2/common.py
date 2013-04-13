"""
Common utilities
"""

import struct


##
# General purpose
#
def map_namespace(prefix, ns):
    """
    Take the namespace prefix, list all constants and build two
    dictionaries -- straight and reverse mappings. E.g.:

    ## neighbor attributes
    NDA_UNSPEC = 0
    NDA_DST = 1
    NDA_LLADDR = 2
    NDA_CACHEINFO = 3
    NDA_PROBES = 4
    (NDA_NAMES, NDA_VALUES) = map_namespace("NDA", globals())

    Will lead to:

    NDA_NAMES = {"NDA_UNSPEC": 0,
                 ...
                 "NDA_PROBES": 4}
    NDA_VALUES = {0: "NDA_UNSPEC",
                  ...
                  4: "NDA_PROBES"}

    """
    by_name = dict([(i, ns[i]) for i in ns.keys() if i.startswith(prefix)])
    by_value = dict([(ns[i], i) for i in ns.keys() if i.startswith(prefix)])
    return (by_name, by_value)


def hexdump(payload, length=0):
    """
    Represent byte string as hex -- for debug purposes
    """
    return ":".join("{0:02x}".format(ord(c))
                    for c in payload[:length] or payload)


def unpack(buf, fmt, fields):
    """
    Unpack the byte stream into dictionary, using sctruct.unpack, e.g.:

    result = unpack(buf, "QBB", ("length", "type", "flags"))
    """
    data = buf.read(struct.calcsize(fmt))
    return dict(zip(fields, struct.unpack(fmt, data)))


##
# Byte stram decoding
#
# ALL these routines should accept buffer and length, though not all
# require the length parameter -- that's requirement of API
#
def t_hex(buf, length):
    """
    Dump NLA in hex
    """
    return hexdump(buf.read(length))


def t_ip6ad(buf, length=None):
    """
    Read 16 bytes from buffer and return IPv6 address as a string
    """
    r = struct.unpack("=BBBBBBBBBBBBBBBB", buf.read(16))
    return "%x%x:%x%x:%x%x:%x%x:%x%x:%x%x:%x%x:%x%x" % \
           (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8],
            r[9], r[10], r[11], r[12], r[13], r[14], r[15])


def t_ip4ad(buf, length):
    """
    Read 4 bytes and return IPv4 address as a string
    """
    r = struct.unpack("=BBBB", buf.read(4))
    return "%u.%u.%u.%u" % (r[0], r[1], r[2], r[3])


def t_l2ad(buf, length):
    """
    Read 6 bytes and return MAC address as a string
    """
    r = struct.unpack("=BBBBBB", buf.read(6))
    return "%x:%x:%x:%x:%x:%x" % (r[0], r[1], r[2], r[3], r[4], r[5])


def t_asciiz(buf, length):
    """
    Read ASCII string of required length from buffer. Since it is used
    to read zero-terminated strings, drop the last byte.
    """
    return buf.read(length - 1)


def t_none(buf, length):
    """
    Read none, return none. Just as a placeholder.
    """
    return None


def t_uint8(buf, length):
    """
    Read and return 8bit unsigned int.
    """
    return struct.unpack("=B", buf.read(1))[0]


def t_uint16(buf, length):
    """
    Read and return 16bit unsigned int.
    """
    return struct.unpack("=H", buf.read(2))[0]


def t_uint32(buf, length):
    """
    Read and return 32bit unsigned int.
    """
    return struct.unpack("=I", buf.read(4))[0]
