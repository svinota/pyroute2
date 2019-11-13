import os
import json
import errno
import select
import struct
import threading
import subprocess
from fcntl import ioctl
from pyroute2 import config
from pyroute2.common import map_enoent
from pyroute2.netlink.rtnl.ifinfmsg import IFT_TUN
from pyroute2.netlink.rtnl.ifinfmsg import IFT_TAP
from pyroute2.netlink.rtnl.ifinfmsg import IFT_NO_PI
from pyroute2.netlink.rtnl.ifinfmsg import IFT_ONE_QUEUE
from pyroute2.netlink.rtnl.ifinfmsg import IFT_VNET_HDR
from pyroute2.netlink.rtnl.ifinfmsg import IFT_MULTI_QUEUE
from pyroute2.netlink.rtnl.ifinfmsg import RTM_NEWLINK
from pyroute2.netlink.rtnl import RTM_VALUES
from pyroute2.netlink.rtnl.riprsocket import RawIPRSocket
from pyroute2.netlink.exceptions import NetlinkError


_BONDING_MASTERS = '/sys/class/net/bonding_masters'
_BONDING_SLAVES = '/sys/class/net/%s/bonding/slaves'
_BRIDGE_MASTER = '/sys/class/net/%s/brport/bridge/ifindex'
_BONDING_MASTER = '/sys/class/net/%s/master/ifindex'
IFNAMSIZ = 16

TUNDEV = '/dev/net/tun'
PLATFORMS = ('i386', 'i686', 'x86_64', 'armv6l', 'armv7l', 's390x', 'aarch64')
if config.machine in PLATFORMS:
    TUNSETIFF = 0x400454ca
    TUNSETPERSIST = 0x400454cb
    TUNSETOWNER = 0x400454cc
    TUNSETGROUP = 0x400454ce
elif config.machine in ('ppc64', 'mips'):
    TUNSETIFF = 0x800454ca
    TUNSETPERSIST = 0x800454cb
    TUNSETOWNER = 0x800454cc
    TUNSETGROUP = 0x800454ce
else:
    TUNSETIFF = None


def sync(f):
    '''
    A decorator to wrap up external utility calls.

    A decorated function receives a netlink message
    as a parameter, and then:

    1. Starts a monitoring thread
    2. Performs the external call
    3. Waits for a netlink event specified by `msg`
    4. Joins the monitoring thread

    If the wrapped function raises an exception, the
    monitoring thread will be forced to stop via the
    control channel pipe. The exception will be then
    forwarded.
    '''
    def monitor(event, ifname, cmd):
        with RawIPRSocket() as ipr:
            poll = select.poll()
            poll.register(ipr, select.POLLIN | select.POLLPRI)
            poll.register(cmd, select.POLLIN | select.POLLPRI)
            ipr.bind()
            while True:
                events = poll.poll()
                for (fd, event) in events:
                    if fd == ipr.fileno():
                        msgs = ipr.get()
                        for msg in msgs:
                            if msg.get('event') == event and \
                                    msg.get_attr('IFLA_IFNAME') == ifname:
                                return
                    else:
                        return

    def decorated(msg):
        rcmd, cmd = os.pipe()
        t = threading.Thread(target=monitor,
                             args=(RTM_VALUES[msg['header']['type']],
                                   msg.get_attr('IFLA_IFNAME'),
                                   rcmd))
        t.start()
        ret = None
        try:
            ret = f(msg)
        except Exception:
            raise
        finally:
            os.write(cmd, b'q')
            t.join()
            os.close(rcmd)
            os.close(cmd)
        return ret

    return decorated


def proxy_setlink(msg, nl):

    def get_interface(index):
        msg = nl.get_links(index)[0]
        try:
            kind = msg.get_attr('IFLA_LINKINFO').get_attr('IFLA_INFO_KIND')
        except AttributeError:
            kind = 'unknown'
        return {'ifname': msg.get_attr('IFLA_IFNAME'),
                'master': msg.get_attr('IFLA_MASTER'),
                'kind': kind}

    forward = True

    # is it a port setup?
    master = msg.get_attr('IFLA_MASTER')
    if master is not None:

        if master == 0:
            # port delete
            # 1. get the current master
            iface = get_interface(msg['index'])
            master = get_interface(iface['master'])
            cmd = 'del'
        else:
            # port add
            # 1. get the master
            master = get_interface(master)
            cmd = 'add'

        ifname = msg.get_attr('IFLA_IFNAME') or \
            get_interface(msg['index'])['ifname']

        # 2. manage the port
        forward_map = {'team': manage_team_port}
        if master['kind'] in forward_map:
            func = forward_map[master['kind']]
            forward = func(cmd, master['ifname'], ifname, nl)

    if forward is not None:
        return {'verdict': 'forward',
                'data': msg.data}


def proxy_newlink(msg, nl):
    kind = None

    # get the interface kind
    linkinfo = msg.get_attr('IFLA_LINKINFO')
    if linkinfo is not None:
        kind = [x[1] for x in linkinfo['attrs']
                if x[0] == 'IFLA_INFO_KIND']
        if kind:
            kind = kind[0]

    if kind == 'tuntap':
        return manage_tuntap(msg)
    elif kind == 'team':
        return manage_team(msg)

    return {'verdict': 'forward',
            'data': msg.data}


@map_enoent
@sync
def manage_team(msg):

    if msg['header']['type'] != RTM_NEWLINK:
        raise ValueError('wrong command type')

    config = {'device': msg.get_attr('IFLA_IFNAME'),
              'runner': {'name': 'activebackup'},
              'link_watch': {'name': 'ethtool'}}

    with open(os.devnull, 'w') as fnull:
        subprocess.check_call(['teamd', '-d', '-n', '-c', json.dumps(config)],
                              stdout=fnull,
                              stderr=fnull)


@map_enoent
def manage_team_port(cmd, master, ifname, nl):
    with open(os.devnull, 'w') as fnull:
        subprocess.check_call(['teamdctl', master, 'port',
                               'remove' if cmd == 'del' else 'add', ifname],
                              stdout=fnull,
                              stderr=fnull)


@sync
def manage_tuntap(msg):

    if TUNSETIFF is None:
        raise NetlinkError(errno.EOPNOTSUPP, 'Arch not supported')

    if msg['header']['type'] != RTM_NEWLINK:
        raise NetlinkError(errno.EOPNOTSUPP, 'Unsupported event')

    ifru_flags = 0
    linkinfo = msg.get_attr('IFLA_LINKINFO')
    infodata = linkinfo.get_attr('IFLA_INFO_DATA')

    flags = infodata.get_attr('IFTUN_IFR', None)
    if infodata.get_attr('IFTUN_MODE') == 'tun':
        ifru_flags |= IFT_TUN
    elif infodata.get_attr('IFTUN_MODE') == 'tap':
        ifru_flags |= IFT_TAP
    else:
        raise ValueError('invalid mode')
    if flags is not None:
        if flags['no_pi']:
            ifru_flags |= IFT_NO_PI
        if flags['one_queue']:
            ifru_flags |= IFT_ONE_QUEUE
        if flags['vnet_hdr']:
            ifru_flags |= IFT_VNET_HDR
        if flags['multi_queue']:
            ifru_flags |= IFT_MULTI_QUEUE
    ifr = msg.get_attr('IFLA_IFNAME')
    if len(ifr) > IFNAMSIZ:
        raise ValueError('ifname too long')
    ifr += (IFNAMSIZ - len(ifr)) * '\0'
    ifr = ifr.encode('ascii')
    ifr += struct.pack('H', ifru_flags)

    user = infodata.get_attr('IFTUN_UID')
    group = infodata.get_attr('IFTUN_GID')
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
