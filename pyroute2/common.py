'''
Common utilities
'''
import re
import os
import sys
import struct
import logging
import platform
import threading
import traceback

from socket import AF_INET
from socket import inet_pton
from socket import inet_ntop
from socket import inet_aton

try:
    basestring = basestring
except NameError:
    basestring = (str, bytes)

AF_PIPE = 255  # Right now AF_MAX == 40
DEFAULT_RCVBUF = 16384
ANCIENT = (platform.dist()[0] in ('redhat', 'centos') and
           platform.dist()[1].startswith('6.') or
           os.environ.get('PYROUTE2_ANCIENT', False))

size_suffixes = {'b': 1,
                 'k': 1024,
                 'kb': 1024,
                 'm': 1024 * 1024,
                 'mb': 1024 * 1024,
                 'g': 1024 * 1024 * 1024,
                 'gb': 1024 * 1024 * 1024,
                 'kbit': 1024 / 8,
                 'mbit': 1024 * 1024 / 8,
                 'gbit': 1024 * 1024 * 1024 / 8}


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
# Debug
#
_log_configured = False


def debug(f):
    '''
    Debug decorator, that logs all the function calls
    '''
    if os.environ.get('DEBUG', None) is None:
        return f

    global _log_configured
    # some nosetests bug prevents the rest of this function
    # being marked as "covered", despite it really IS; so
    # FIXME: trace and file nosetests bug
    # possibly related to the log capture
    if not _log_configured:
        _log_configured = True
        filename = os.environ.get('DEBUG_FILE', None)
        logging.basicConfig(filename=filename,
                            level=logging.DEBUG)

    def wrap(*argv, **kwarg):
        tid = id(threading.current_thread())
        bt = ''.join(traceback.format_stack()[:-1])
        logging.debug("%s %s: bt: %s" % (tid, f.__name__, bt))
        logging.debug("%s %s: call: %s; %s" % (tid,
                                               f.__name__,
                                               argv,
                                               kwarg))
        ret = f(*argv, **kwarg)
        logging.debug("%s %s: ret: %s" % (tid, f.__name__, ret))
        return ret

    return wrap


##
# General purpose
#
class Dotkeys(dict):
    '''
    This is a sick-minded hack of dict, intended to be an eye-candy.
    It allows to get dict's items byt dot reference:

    ipdb["lo"] == ipdb.lo
    ipdb["eth0"] == ipdb.eth0

    Obviously, it will not work for some cases, like unicode names
    of interfaces and so on. Beside of that, it introduces some
    complexity.

    But it simplifies live for old-school admins, who works with good
    old "lo", "eth0", and like that naming schemes.
    '''
    var_name = re.compile('^[a-zA-Z_]+[a-zA-Z_0-9]*$')

    def __dir__(self):
        return [i for i in self if
                type(i) == str and self.var_name.match(i)]

    def __getattribute__(self, key, *argv):
        try:
            return dict.__getattribute__(self, key)
        except AttributeError as e:
            if key == '__deepcopy__':
                raise e
            return self[key]

    def __setattr__(self, key, value):
        if key in self:
            self[key] = value
        else:
            dict.__setattr__(self, key, value)

    def __delattr__(self, key):
        if key in self:
            del self[key]
        else:
            dict.__delattr__(self, key)


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


def list_subnet(dqn, mask, family=AF_INET):
    '''
    List all IPs in the network
    '''
    if family != AF_INET:
        raise NotImplementedError('please report the issue')

    ret = []
    net = struct.unpack('>I', inet_pton(family, dqn))[0]
    shift = 32 - mask
    for host in range(1, 2 ** shift):
        ret.append(inet_ntop(family, struct.pack('>I', net | host)))
    return ret


def dqn2int(mask):
    '''
    IPv4 dotted quad notation to int mask conversion
    '''
    return bin(struct.unpack('>L', inet_aton(mask))[0]).count('1')


def hexdump(payload, length=0):
    '''
    Represent byte string as hex -- for debug purposes
    '''
    if sys.version[0] == '3':
        return ':'.join('{0:02x}'.format(c)
                        for c in payload[:length] or payload)
    else:
        return ':'.join('{0:02x}'.format(ord(c))
                        for c in payload[:length] or payload)


class AddrPool(object):
    '''
    Address pool
    '''
    cell = 0xffffffffffffffff

    def __init__(self, minaddr=0xf, maxaddr=0xffffff, reverse=False):
        self.cell_size = 0  # in bits
        mx = self.cell
        self.reverse = reverse
        self.ban = []
        while mx:
            mx >>= 8
            self.cell_size += 1
        self.cell_size *= 8
        # calculate, how many ints we need to bitmap all addresses
        self.cells = int((maxaddr - minaddr) / self.cell_size + 1)
        # initial array
        self.addr_map = [self.cell]
        self.minaddr = minaddr
        self.maxaddr = maxaddr
        self.lock = threading.RLock()

    def alloc(self):
        with self.lock:
            # gc self.ban:
            for item in tuple(self.ban):
                if item['counter'] == 0:
                    self.free(item['addr'])
                    self.ban.remove(item)
                else:
                    item['counter'] -= 1

            # iterate through addr_map
            base = 0
            for cell in self.addr_map:
                if cell:
                    # not allocated addr
                    bit = 0
                    while True:
                        if (1 << bit) & self.addr_map[base]:
                            self.addr_map[base] ^= 1 << bit
                            break
                        bit += 1
                    ret = (base * self.cell_size + bit)

                    if self.reverse:
                        ret = self.maxaddr - ret
                    else:
                        ret = ret + self.minaddr

                    if self.minaddr <= ret <= self.maxaddr:
                        return ret
                    else:
                        self.free(ret)
                        raise KeyError('no free address available')

                base += 1
            # no free address available
            if len(self.addr_map) < self.cells:
                # create new cell to allocate address from
                self.addr_map.append(self.cell)
                return self.alloc()
            else:
                raise KeyError('no free address available')

    def free(self, addr, ban=0):
        with self.lock:
            if ban != 0:
                self.ban.append({'addr': addr,
                                 'counter': ban})
            else:
                if self.reverse:
                    addr = self.maxaddr - addr
                else:
                    addr -= self.minaddr
                base = addr // self.cell_size
                bit = addr % self.cell_size
                if len(self.addr_map) <= base:
                    raise KeyError('address is not allocated')
                if self.addr_map[base] & (1 << bit):
                    raise KeyError('address is not allocated')
                self.addr_map[base] ^= 1 << bit
