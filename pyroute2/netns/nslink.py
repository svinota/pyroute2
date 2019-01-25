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
    netns = NetNS('test', flags=os.O_CREAT | os.O_EXCL)

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
import signal
import atexit
import logging
from functools import partial
from pyroute2.netlink.rtnl.iprsocket import MarshalRtnl
from pyroute2.iproute import RTNL_API
from pyroute2.netns import setns
from pyroute2.netns import remove
from pyroute2.remote import Server
from pyroute2.remote import Transport
from pyroute2.remote import RemoteSocket

log = logging.getLogger(__name__)


class FD(object):

    def __init__(self, fd):
        self.fd = fd
        for name in ('read', 'write', 'close'):
            setattr(self, name, partial(getattr(os, name), self.fd))

    def fileno(self):
        return self.fd

    def flush(self):
        return None


class NetNS(RTNL_API, RemoteSocket):
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
        trnsp_in, self.remote_trnsp_out = [Transport(FD(x))
                                           for x in os.pipe()]
        self.remote_trnsp_in, trnsp_out = [Transport(FD(x))
                                           for x in os.pipe()]

        self.child = os.fork()
        if self.child == 0:
            # child process
            trnsp_in.close()
            trnsp_out.close()
            try:
                setns(self.netns, self.flags)
            except OSError as e:
                (self
                 .remote_trnsp_out
                 .send({'stage': 'init', 'error': e}))
                os._exit(e.errno)
            except Exception as e:
                (self.
                 remote_trnsp_out
                 .send({'stage': 'init',
                        'error': OSError(errno.ECOMM,
                                         str(e),
                                         self.netns)}))
                os._exit(255)

            try:
                Server(self.remote_trnsp_in, self.remote_trnsp_out)
            finally:
                os._exit(0)

        try:
            self.remote_trnsp_in.close()
            self.remote_trnsp_out.close()
            super(NetNS, self).__init__(trnsp_in, trnsp_out)
        except Exception:
            self.close()
            raise
        atexit.register(self.close)
        self.marshal = MarshalRtnl()

    def clone(self):
        return type(self)(self.netns, self.flags)

    def _cleanup_atexit(self):
        if hasattr(atexit, 'unregister'):
            atexit.unregister(self.close)
        else:
            try:
                atexit._exithandlers.remove((self.close, (), {}))
            except ValueError:
                pass

    def close(self):
        self._cleanup_atexit()
        try:
            super(NetNS, self).close()
        except:
            # something went wrong, force server shutdown
            try:
                self.trnsp_out.send({'stage': 'shutdown'})
            except Exception:
                pass
            log.error('forced shutdown procedure, clean up netns manually')

        try:
            os.kill(self.child, signal.SIGTERM)
            os.waitpid(self.child, 0)
        except OSError:
            pass

    def post_init(self):
        pass

    def remove(self):
        '''
        Try to remove this network namespace from the system.
        '''
        remove(self.netns)
