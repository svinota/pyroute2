'''
NetNS
=====

A NetNS object is IPRoute-like. It runs in the main network
namespace, but also creates a proxy process running in
the required netns. All the netlink requests are done via
that proxy process.

NetNS supports standard IPRoute API, so can be used instead
of IPRoute, e.g., in IPDB::

    # start the main network settings database:
    ipdb_main = IPDB()
    # start the same for a netns:
    ipdb_test = IPDB(nl=NetNS('test'))

    # create VETH
    ipdb_main.create(ifname='v0p0', kind='veth', peer='v0p1').commit()

    # move peer VETH into the netns
    with ipdb_main.interfaces.v0p1 as veth:
        veth.net_ns_fd = 'test'

    # please keep in mind, that netns move clears all the settings
    # on a VETH interface pair, so one should run netns assignment
    # as a separate operation only

    # assign addresses
    # please notice, that `v0p1` is already in the `test` netns,
    # so should be accessed via `ipdb_test`
    with ipdb_main.interfaces.v0p0 as veth:
        veth.add_ip('172.16.200.1/24')
        veth.up()
    with ipdb_test.interfaces.v0p1 as veth:
        veth.add_ip('172.16.200.2/24')
        veth.up()

Please review also the test code, under `tests/test_netns.py` for
more examples.

By default, NetNS creates requested netns, if it doesn't exist,
or uses existing one. To control this behaviour, one can use flags
as for `open(2)` system call::

    # create a new netns or fail, if it already exists
    netns = NetNS('test', flags=os.O_CREAT | os.O_EXIST)

    # create a new netns or use existing one
    netns = NetNS('test', flags=os.O_CREAT)

    # the same as above, the default behaviour
    netns = NetNS('test')

To remove a network namespace::

    from pyroute2 import NetNS
    netns = NetNS('test')
    netns.close()
    netns.remove()

One should stop it first with `close()`, and only after that
run `remove()`.

'''

import os
import errno
import atexit
import signal
import logging
from pyroute2.config import MpPipe
from pyroute2.config import MpProcess
from pyroute2.netlink.rtnl.iprsocket import MarshalRtnl
from pyroute2.iproute import IPRouteMixin
from pyroute2.netns import setns
from pyroute2.netns import remove
from pyroute2.remote import Server
from pyroute2.remote import RemoteSocket

logging.basicConfig()
log = logging.getLogger(__name__)


def NetNServer(netns, cmdch, brdch, flags=os.O_CREAT):
    '''
    The netns server supposed to be started automatically by NetNS.
    It has two communication channels: one simplex to forward incoming
    netlink packets, `rcvch`, and other synchronous duplex to get
    commands and send back responses, `cmdch`.

    Channels should support standard socket API, should be compatible
    with poll/select and should be able to transparently pickle objects.
    NetNS uses `multiprocessing.Pipe` for this purpose, but it can be
    any other implementation with compatible API.

    The first parameter, `netns`, is a netns name. Depending on the
    `flags`, the netns can be created automatically. The `flags` semantics
    is exactly the same as for `open(2)` system call.

    ...

    The server workflow is simple. The startup sequence::

        1. Create or open a netns.

        2. Start `IPRoute` instance. It will be used only on the low level,
           the `IPRoute` will not parse any packet.

        3. Start poll/select loop on `cmdch` and `IPRoute`.

    On the startup, the server sends via `cmdch` the status packet. It can be
    `None` if all is OK, or some exception.

    Further data handling, depending on the channel, server side::

        1. `IPRoute`: read an incoming netlink packet and send it unmodified
           to the peer via `rcvch`. The peer, polling `rcvch`, can handle
           the packet on its side.

        2. `cmdch`: read tuple (cmd, argv, kwarg). If the `cmd` starts with
           "send", then take `argv[0]` as a packet buffer, treat it as one
           netlink packet and substitute PID field (offset 12, uint32) with
           its own. Strictly speaking, it is not mandatory for modern netlink
           implementations, but it is required by the protocol standard.

    '''
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        nsfd = setns(netns, flags)
    except OSError as e:
        cmdch.send({'stage': 'init',
                    'error': e})
        return e.errno
    except Exception as e:
        cmdch.send({'stage': 'init',
                    'error': OSError(errno.ECOMM, str(e), netns)})
        return 255

    Server(cmdch, brdch)
    os.close(nsfd)


class NetNS(IPRouteMixin, RemoteSocket):
    '''
    NetNS is the IPRoute API with network namespace support.

    **Why not IPRoute?**

    The task to run netlink commands in some network namespace, being in
    another network namespace, requires the architecture, that differs
    too much from a simple Netlink socket.

    NetNS starts a proxy process in a network namespace and uses
    `multiprocessing` communication channels between the main and the proxy
    processes to route all `recv()` and `sendto()` requests/responses.

    **Any specific API calls?**

    Nope. `NetNS` supports all the same, that `IPRoute` does, in the same
    way. It provides full `socket`-compatible API and can be used in
    poll/select as well.

    The only difference is the `close()` call. In the case of `NetNS` it
    is **mandatory** to close the socket before exit.

    **NetNS and IPDB**

    It is possible to run IPDB with NetNS::

        from pyroute2 import NetNS
        from pyroute2 import IPDB

        ip = IPDB(nl=NetNS('somenetns'))
        ...
        ip.release()

    Do not forget to call `release()` when the work is done. It will shut
    down `NetNS` instance as well.
    '''
    def __init__(self, netns, flags=os.O_CREAT):
        self.netns = netns
        self.flags = flags
        self.cmdch, self._cmdch = MpPipe()
        self.brdch, self._brdch = MpPipe()
        atexit.register(self.close)
        self.server = MpProcess(target=NetNServer,
                                args=(self.netns,
                                      self._cmdch,
                                      self._brdch,
                                      self.flags))
        self.server.start()
        super(NetNS, self).__init__()
        self.marshal = MarshalRtnl()

    def clone(self):
        return type(self)(self.netns, self.flags)

    def close(self):
        try:
            super(NetNS, self).close()
        except:
            # something went wrong, force server shutdown
            self.cmdch.send({'stage': 'shutdown'})
            log.error('forced shutdown procedure, clean up netns manually')
        # force cleanup command channels
        self.cmdch.close()
        self.brdch.close()
        self._cmdch.close()
        self._brdch.close()
        # join the server
        self.server.join()

    def post_init(self):
        pass

    def remove(self):
        '''
        Try to remove this network namespace from the system.
        '''
        remove(self.netns)
