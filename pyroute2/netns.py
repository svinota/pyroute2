'''
NetNS, network namespaces support
=================================

Pyroute2 provides basic network namespaces support. The core
class is `NetNS`.

Please be aware, that in order to run `setns()` system call
the library uses `ctypes` module. It can fail on platforms
where SELinux is enforced. If the Python interpreter, loading
this module, dumps the core, one can check the SELinux state
with `getenforce` command.

classes
-------
'''

import os
import ctypes
import select
import struct
import threading
import traceback
import multiprocessing as mp
from socket import SOL_SOCKET
from socket import SO_RCVBUF
from pyroute2 import IPRoute
from pyroute2.netlink.nlsocket import NetlinkMixin
from pyroute2.netlink.rtnl import IPRSocketMixin
from pyroute2.iproute import IPRouteMixin

__NR_setns = 308  # FIXME
CLONE_NEWNET = 0x40000000


def server(netns, rcvch, cmdch):
    nsfd = os.open('/var/run/netns/%s' % netns, os.O_RDONLY)
    libc = ctypes.CDLL('libc.so.6')
    libc.syscall(__NR_setns, nsfd, CLONE_NEWNET)
    ipr = IPRoute()
    poll = select.poll()
    poll.register(ipr, select.POLLIN | select.POLLPRI)
    poll.register(cmdch, select.POLLIN | select.POLLPRI)
    while True:
        events = poll.poll()
        for (fd, event) in events:
            if fd == ipr.fileno():
                bufsize = ipr.getsockopt(SOL_SOCKET, SO_RCVBUF) // 2
                rcvch.send(ipr.recv(bufsize))
            elif fd == cmdch.fileno():
                try:
                    cmdline = cmdch.recv()
                    if cmdline is None:
                        poll.unregister(ipr)
                        poll.unregister(cmdch)
                        ipr.close()
                        os.close(nsfd)
                        return
                    (cmd, argv, kwarg) = cmdline
                    if cmd[:4] == 'send':
                        # Achtung
                        #
                        # It's a hack, but we just have to do it: one
                        # must use actual pid in netlink messages
                        #
                        # FIXME: there can be several messages in one
                        # call buffer; but right now we can ignore it
                        msg = argv[0][:12]
                        msg += struct.pack("I", os.getpid())
                        msg += argv[0][16:]
                        argv = list(argv)
                        argv[0] = msg
                    cmdch.send(getattr(ipr, cmd)(*argv, **kwarg))
                except Exception as e:
                    e.tb = traceback.format_exc()
                    cmdch.send(e)


class NetNSProxy(object):

    netns = 'default'

    def __init__(self, *argv, **kwarg):
        self.cmdlock = threading.Lock()
        self.rcvch, rcvch = mp.Pipe()
        self.cmdch, cmdch = mp.Pipe()
        self.server = mp.Process(target=server,
                                 args=(self.netns, rcvch, cmdch))
        self.server.start()

    def recv(self, bufsize):
        return self.rcvch.recv()

    def close(self):
        self.cmdch.send(None)
        self.server.join()

    def proxy(self, cmd, *argv, **kwarg):
        with self.cmdlock:
            self.cmdch.send((cmd, argv, kwarg))
            response = self.cmdch.recv()
            if isinstance(response, Exception):
                raise response
            return response

    def fileno(self):
        return self.rcvch.fileno()

    def bind(self, *argv, **kwarg):
        if 'async' in kwarg:
            kwarg['async'] = False
        return self.proxy('bind', *argv, **kwarg)

    def send(self, *argv, **kwarg):
        return self.proxy('send', *argv, **kwarg)

    def sendto(self, *argv, **kwarg):
        return self.proxy('sendto', *argv, **kwarg)

    def getsockopt(self, *argv, **kwarg):
        return self.proxy('getsockopt', *argv, **kwarg)

    def setsockopt(self, *argv, **kwarg):
        return self.proxy('setsockopt', *argv, **kwarg)


class NetNSocket(NetlinkMixin, NetNSProxy):
    def bind(self, *argv, **kwarg):
        return NetNSProxy.bind(self, *argv, **kwarg)


class NetNSIPR(IPRSocketMixin, NetNSocket):
    pass


class NetNS(IPRouteMixin, NetNSIPR):
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
    def __init__(self, netns):
        self.netns = netns
        super(NetNS, self).__init__()
