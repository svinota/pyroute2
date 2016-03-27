'''
Netns management overview
=========================

Pyroute2 provides basic namespaces management support.
Here's a quick overview of typical netns tasks and
related pyroute2 tools.

Move an interface to a namespace
--------------------------------

Though this task is managed not via `netns` module, it
should be mentioned here as well. To move an interface
to a netns, one should provide IFLA_NET_NS_FD nla in
a set link RTNL request. The nla is an open FD number,
that refers to already created netns. The pyroute2
library provides also a possibility to specify not a
FD number, but a netns name as a string. In that case
the library will try to lookup the corresponding netns
in the standard location.

Create veth and move the peer to a netns with IPRoute::

    from pyroute2 import IPRoute
    ipr = IPRoute()
    ipr.link('add', ifname='v0p0', kind='veth', peer='v0p1')
    idx = ipr.link_lookup(ifname='v0p1')[0]
    ipr.link('set', index=idx, net_ns_fd='netns_name')

Create veth and move the peer to a netns with IPDB::

    from pyroute2 import IPDB
    ipdb = IPDB()
    ipdb.create(ifname='v0p0', kind='veth', peer='v0p1').commit()
    with ipdb.interfaces.v0p1 as i:
        i.net_ns_fd = 'netns_name'

Manage interfaces within a netns
--------------------------------

This task can be done with `NetNS` objects. A `NetNS` object
spawns a child and runs it within a netns, providing the same
API as `IPRoute` does::

    from pyroute2 import NetNS
    ns = NetNS('netns_name')
    # do some stuff within the netns
    ns.close()

One can even start `IPDB` on the top of `NetNS`::

    from pyroute2 import NetNS
    from pyroute2 import IPDB
    ipdb = IPDB(nl=NetNS('netns_name'))
    # do some stuff within the netns
    ipdb.release()

Spawn a process within a netns
------------------------------

For that purpose one can use `NSPopen` API. It works just
as normal `Popen`, but starts a process within a netns.

List, set, create and remove netns
----------------------------------

These functions are described below. To use them, import
`netns` module::

    from pyroute2 import netns
    netns.listnetns()

Please be aware, that in order to run system calls the
library uses `ctypes` module. It can fail on platforms
where SELinux is enforced. If the Python interpreter,
loading this module, dumps the core, one can check the
SELinux state with `getenforce` command.

'''

import os
import errno
import ctypes
from pyroute2 import config

# FIXME: arch reference
__NR = {'x86_': {'64bit': 308},
        'i386': {'32bit': 346},
        'i686': {'32bit': 346},
        'mips': {'32bit': 4344,
                 '64bit': 5303},  # FIXME: NABI32?
        'armv': {'32bit': 375,
                 '64bit': 375}}  # FIXME: EABI vs. OABI?
__NR_setns = __NR.get(config.machine[:4], {}).get(config.arch, 308)

CLONE_NEWNET = 0x40000000
MNT_DETACH = 0x00000002
MS_BIND = 4096
MS_REC = 16384
MS_SHARED = 1 << 20
NETNS_RUN_DIR = '/var/run/netns'


def listnetns():
    '''
    List available network namespaces.
    '''
    try:
        return os.listdir(NETNS_RUN_DIR)
    except OSError as e:
        if e.errno == errno.ENOENT:
            return []
        else:
            raise


def create(netns, libc=None):
    '''
    Create a network namespace.
    '''
    libc = libc or ctypes.CDLL('libc.so.6', use_errno=True)
    # FIXME validate and prepare NETNS_RUN_DIR

    netnspath = '%s/%s' % (NETNS_RUN_DIR, netns)
    netnspath = netnspath.encode('ascii')
    netnsdir = NETNS_RUN_DIR.encode('ascii')

    # init netnsdir
    try:
        os.mkdir(netnsdir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    # this code is ported from iproute2
    done = False
    while libc.mount(b'', netnsdir, b'none', MS_SHARED | MS_REC, None) != 0:
        if done:
            raise OSError(ctypes.get_errno(), 'share rundir failed', netns)
        if libc.mount(netnsdir, netnsdir, b'none', MS_BIND, None) != 0:
            raise OSError(ctypes.get_errno(), 'mount rundir failed', netns)
        done = True

    # create mountpoint
    os.close(os.open(netnspath, os.O_RDONLY | os.O_CREAT | os.O_EXCL, 0))

    # unshare
    if libc.unshare(CLONE_NEWNET) < 0:
        raise OSError(ctypes.get_errno(), 'unshare failed', netns)

    # bind the namespace
    if libc.mount(b'/proc/self/ns/net', netnspath, b'none', MS_BIND, None) < 0:
        raise OSError(ctypes.get_errno(), 'mount failed', netns)


def remove(netns, libc=None):
    '''
    Remove a network namespace.
    '''
    libc = libc or ctypes.CDLL('libc.so.6', use_errno=True)
    netnspath = '%s/%s' % (NETNS_RUN_DIR, netns)
    netnspath = netnspath.encode('ascii')
    libc.umount2(netnspath, MNT_DETACH)
    os.unlink(netnspath)


def setns(netns, flags=os.O_CREAT, libc=None):
    '''
    Set netns for the current process.

    The flags semantics is the same as for the `open(2)`
    call:

        - O_CREAT -- create netns, if doesn't exist
        - O_CREAT | O_EXCL -- create only if doesn't exist
    '''
    libc = libc or ctypes.CDLL('libc.so.6', use_errno=True)
    netnspath = '%s/%s' % (NETNS_RUN_DIR, netns)
    netnspath = netnspath.encode('ascii')

    if netns in listnetns():
        if flags & (os.O_CREAT | os.O_EXCL) == (os.O_CREAT | os.O_EXCL):
            raise OSError(errno.EEXIST, 'netns exists', netns)
    else:
        if flags & os.O_CREAT:
            create(netns, libc=libc)

    nsfd = os.open(netnspath, os.O_RDONLY)
    ret = libc.syscall(__NR_setns, nsfd, CLONE_NEWNET)
    if ret != 0:
        raise OSError(ctypes.get_errno(), 'failed to open netns', netns)
    return nsfd
