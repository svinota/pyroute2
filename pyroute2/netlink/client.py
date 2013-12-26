from pyroute2.netlink import Marshal
from pyroute2.netlink.generic import NETLINK_GENERIC
from pyroute2.iocore.iocore import IOCore


class Netlink(IOCore):
    '''
    Main netlink messaging class. It automatically spawns threads
    to monitor network and netlink I/O, creates and destroys message
    queues.

    By default, netlink class connects to the local netlink socket
    on startup. If you prefer to connect to another host, use::

        nl = Netlink(host='tcp://remote.host:7000')

    It is possible to connect to uplinks after the startup::

        nl = Netlink(do_connect=False)
        nl.connect('tcp://remote.host:7000')

    To act as a server, call serve()::

        nl = Netlink()
        nl.serve('unix:///tmp/pyroute')
    '''
    family = NETLINK_GENERIC
    groups = 0
    marshal = Marshal
    name = 'Netlink API'
    do_connect = True
