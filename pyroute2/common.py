"""
Common utilities
"""


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
