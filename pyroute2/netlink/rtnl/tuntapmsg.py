import os
import struct
import platform
from fcntl import ioctl
from pyroute2.netlink import nla
from pyroute2.netlink import nlmsg

IFNAMSIZ = 16

TUNDEV = '/dev/net/tun'
arch = platform.machine()
if arch == 'x86_64':
    TUNSETIFF = 0x400454ca
    TUNSETPERSIST = 0x400454cb
    TUNSETOWNER = 0x400454cc
    TUNSETGROUP = 0x400454ce
elif arch == 'ppc64':
    TUNSETIFF = 0x800454ca
    TUNSETPERSIST = 0x800454cb
    TUNSETOWNER = 0x800454cc
    TUNSETGROUP = 0x800454ce
else:
    TUNSETIFF = None

IFF_TUN = 0x0001
IFF_TAP = 0x0002
IFF_NO_PI = 0x1000
IFF_ONE_QUEUE = 0x2000
IFF_VNET_HDR = 0x4000
IFF_TUN_EXCL = 0x8000
IFF_MULTI_QUEUE = 0x0100
IFF_ATTACH_QUEUE = 0x0200
IFF_DETACH_QUEUE = 0x0400
# read-only
IFF_PERSIST = 0x0800
IFF_NOFILTER = 0x1000


class tuntapmsg(nlmsg):
    '''
    Custom message type

    Create/delete tuntap device
    '''
    prefix = 'IFTUN_'

    # fields should be compatible with ifinfmsg, since
    # these packets will go the same way down to the socket
    fields = (('family', 'B'),
              ('__align', 'B'),
              ('ifi_type', 'H'),
              ('index', 'i'),
              ('flags', 'I'),
              ('change', 'I'))

    nla_map = (('IFTUN_UNSPEC', 'none'),
               ('IFTUN_MODE', 'asciiz'),
               ('IFTUN_UID', 'uint32'),
               ('IFTUN_GID', 'uint32'),
               ('IFTUN_IFNAME', 'asciiz'),
               ('IFTUN_IFR', 'flags'))

    class flags(nla):
        fields = (('no_pi', 'B'),
                  ('one_queue', 'B'),
                  ('vnet_hdr', 'B'),
                  ('tun_excl', 'B'),
                  ('multi_queue', 'B'),
                  ('persist', 'B'),
                  ('nofilter', 'B'))


def tuntap_create(data, rcvch=None):

    if TUNSETIFF is None:
        raise Exception('unsupported arch')

    msg = tuntapmsg(data)
    msg.decode()
    ifru_flags = 0
    flags = msg.get_attr('IFTUN_IFR', None)
    if msg.get_attr('IFTUN_MODE') == 'tun':
        ifru_flags |= IFF_TUN
    else:
        ifru_flags |= IFF_TAP
    if flags is not None:
        if flags['no_pi']:
            ifru_flags |= IFF_NO_PI
        if flags['one_queue']:
            ifru_flags |= IFF_ONE_QUEUE
        if flags['vnet_hdr']:
            ifru_flags |= IFF_VNET_HDR
        if flags['multi_queue']:
            ifru_flags |= IFF_MULTI_QUEUE
    ifr = msg.get_attr('IFTUN_IFNAME')
    if len(ifr) > IFNAMSIZ:
        raise ValueError('ifname too long')
    ifr += (IFNAMSIZ - len(ifr)) * '\0'
    ifr = ifr.encode('ascii')
    ifr += struct.pack('H', ifru_flags)

    user = msg.get_attr('IFTUN_UID')
    group = msg.get_attr('IFTUN_GID')
    #
    fd = os.open(TUNDEV, os.O_RDWR)
    try:
        ioctl(fd, TUNSETIFF, ifr)
        if user is not None:
            ioctl(fd, TUNSETOWNER, user)
        if group is not None:
            ioctl(fd, TUNSETGROUP, group)
        ioctl(fd, TUNSETPERSIST, 1)
    except Exception:
        raise
    finally:
        os.close(fd)
