'''
Common utilities
'''

time_suffixes = {'s': 1,
                 'sec': 1,
                 'secs': 1,
                 'ms': 1000,
                 'msec': 1000,
                 'msecs': 1000,
                 'us': 1000000,
                 'usec': 1000000,
                 'usecs': 1000000}

rate_suffixes = {'bit': 1,
                 'Kibit': 1024,
                 'kbit': 1000,
                 'mibit': 1024 * 1024,
                 'mbit': 1000000,
                 'gibit': 1024 * 1024 * 1024,
                 'gbit': 1000000000,
                 'tibit': 1024 * 1024 * 1024 * 1024,
                 'tbit': 1000000000000,
                 'Bps': 8,
                 'KiBps': 8 * 1024,
                 'KBps': 8000,
                 'MiBps': 8 * 1024 * 1024,
                 'MBps': 8000000,
                 'GiBps': 8 * 1024 * 1024 * 1024,
                 'GBps': 8000000000,
                 'TiBps': 8 * 1024 * 1024 * 1024 * 1024,
                 'TBps': 8000000000000}


##
# General purpose
#
def map_namespace(prefix, ns):
    '''
    Take the namespace prefix, list all constants and build two
    dictionaries -- straight and reverse mappings. E.g.:

    ## neighbor attributes
    NDA_UNSPEC = 0
    NDA_DST = 1
    NDA_LLADDR = 2
    NDA_CACHEINFO = 3
    NDA_PROBES = 4
    (NDA_NAMES, NDA_VALUES) = map_namespace('NDA', globals())

    Will lead to:

    NDA_NAMES = {'NDA_UNSPEC': 0,
                 ...
                 'NDA_PROBES': 4}
    NDA_VALUES = {0: 'NDA_UNSPEC',
                  ...
                  4: 'NDA_PROBES'}

    '''
    by_name = dict([(i, ns[i]) for i in ns.keys() if i.startswith(prefix)])
    by_value = dict([(ns[i], i) for i in ns.keys() if i.startswith(prefix)])
    return (by_name, by_value)


def hexdump(payload, length=0):
    '''
    Represent byte string as hex -- for debug purposes
    '''
    return ':'.join('{0:02x}'.format(ord(c))
                    for c in payload[:length] or payload)
