'''
The library provides very basic RTNL API for BSD systems
via protocol emulation. Only getters are supported yet, no
setters.

BSD employs PF_ROUTE sockets to send notifications about
network object changes, but the protocol doesn not allow
changing links/addresses/etc like Netlink.

To change network setting one have to rely on system calls
or external tools. Thus IPRoute on BSD systems is not as
effective as on Linux, where all the changes are done via
Netlink.

The monitoring started with `bind()` is implemented as an
implicit thread, started by the `bind()` call. This is done
to have only one notification FD, used both for normal calls
and notifications. This allows to use IPRoute objects in
poll/select calls.

On Linux systems RTNL API is provided by the netlink protocol,
so no implicit threads are started by default to monitor the
system updates. `IPRoute.bind(...)` may start the async cache
thread, but only when asked explicitly::

    #
    # Normal monitoring. Always starts monitoring thread on
    # FreeBSD / OpenBSD, no threads on Linux.
    #
    with IPRoute() as ipr:
        ipr.bind()
        ...

    #
    # Monitoring with async cache. Always starts cache thread
    # on Linux, ignored on FreeBSD / OpenBSD.
    #
    with IPRoute() as ipr:
        ipr.bind(async_cache=True)
        ...

On all the supported platforms, be it Linux or BSD, the
`IPRoute.recv(...)` method returns valid netlink RTNL raw binary
payload and `IPRoute.get(...)` returns parsed RTNL messages.
'''
import os
import select
import threading

from pyroute2.netlink import (NLM_F_REQUEST,
                              NLM_F_DUMP,
                              NLM_F_MULTI,
                              NLMSG_DONE)

from pyroute2.netlink.rtnl import (RTM_NEWLINK,
                                   RTM_GETLINK,
                                   RTM_NEWADDR,
                                   RTM_GETADDR,
                                   RTM_NEWROUTE,
                                   RTM_GETROUTE,
                                   RTM_NEWNEIGH,
                                   RTM_GETNEIGH)

from pyroute2.bsd.rtmsocket import RTMSocket
from pyroute2.bsd.util import Ifconfig
from pyroute2.netlink.rtnl.marshal import MarshalRtnl
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg
from pyroute2.common import AddrPool
from pyroute2.common import Namespace
from pyroute2.proxy import NetlinkProxy
try:
    import queue
except ImportError:
    import Queue as queue


class IPRoute(object):

    def __init__(self, *argv, **kwarg):
        self._ifc = Ifconfig()
        self.marshal = MarshalRtnl()
        send_ns = Namespace(self, {'addr_pool': AddrPool(0x10000, 0x1ffff),
                                   'monitor': False})
        self._sproxy = NetlinkProxy(policy='return', nl=send_ns)
        self._mon_th = None
        self._rtm = None
        self._pfdr, self._pfdw = os.pipe()  # notify external poll/select
        self._ctlr, self._ctlw = os.pipe()  # notify monitoring thread
        self._outq = queue.Queue()
        self._system_lock = threading.Lock()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        with self._system_lock:
            if self._mon_th is not None:
                os.write(self._ctlw, b'\0')
                self._mon_th.join()
                self._rtm.close()
                for ep in (self._pfdr, self._pfdw, self._ctlr, self._ctlw):
                    try:
                        os.close(ep)
                    except OSError:
                        pass

    def bind(self, *argv, **kwarg):
        with self._system_lock:
            if self._mon_th is not None:
                return

            self._mon_th = threading.Thread(target=self._monitor_thread,
                                            name='PF_ROUTE monitoring')
            self._mon_th.setDaemon(True)
            self._mon_th.start()

    def _monitor_thread(self):
        # Monitoring thread to convert arriving PF_ROUTE data into
        # the netlink format, enqueue it and notify poll/select.
        self._rtm = RTMSocket(output='netlink')
        inputs = [self._rtm.fileno(), self._ctlr]
        outputs = []
        while True:
            try:
                events, _, _ = select.select(inputs, outputs, inputs)
            except:
                continue
            for fd in events:
                if fd == self._ctlr:
                    # Main thread <-> monitor thread protocol is
                    # pretty simple: discard the data and terminate
                    # the monitor thread.
                    os.read(self._ctlr, 1)
                    return
                else:
                    # Read the data from the socket and queue it
                    msg = self._rtm.get()
                    if msg is not None:
                        msg.encode()
                        self._outq.put(msg.data)
                        # Notify external poll/select
                        os.write(self._pfdw, b'\0')

    def fileno(self):
        # Every time when some new data arrives, one should write
        # into self._pfdw one byte to kick possible poll/select.
        #
        # Resp. recv() discards one byte from self._pfdr each call.
        return self._pfdr

    def get(self):
        data = self.recv()
        return self.marshal.parse(data)

    def recv(self, bufsize=None):
        os.read(self._pfdr, 1)
        return self._outq.get()

    def getsockopt(self, *argv, **kwarg):
        return 1024 * 1024

    def sendto_gate(self, msg, addr):
        #
        # handle incoming netlink requests
        #
        # sendto_gate() receives single RTNL messages as objects
        #
        cmd = msg['header']['type']
        flags = msg['header']['flags']
        seq = msg['header']['sequence_number']

        # work only on dump requests for now
        if flags != NLM_F_REQUEST | NLM_F_DUMP:
            return

        #
        if cmd == RTM_GETLINK:
            rtype = RTM_NEWLINK
            ret = self.get_links()
        elif cmd == RTM_GETADDR:
            rtype = RTM_NEWADDR
            ret = self.get_addr()
        elif cmd == RTM_GETROUTE:
            rtype = RTM_NEWROUTE
            ret = self.get_routes()
        elif cmd == RTM_GETNEIGH:
            rtype = RTM_NEWNEIGH
            ret = self.get_neighbours()

        #
        # set response type and finalize the message
        for r in ret:
            r['header']['type'] = rtype
            r['header']['flags'] = NLM_F_MULTI
            r['header']['sequence_number'] = seq

        #
        r = type(msg)()
        r['header']['type'] = NLMSG_DONE
        r['header']['sequence_number'] = seq
        ret.append(r)

        data = b''
        for r in ret:
            r.encode()
            data += r.data
        self._outq.put(data)
        os.write(self._pfdw, b'\0')

    def get_links(self, *argv, **kwarg):
        ret = []
        data = self._ifc.run()
        parsed = self._ifc.parse(data)
        for name, spec in parsed['links'].items():
            msg = ifinfmsg().load(spec)
            del msg['value']
            ret.append(msg)
        return ret

    def get_addr(self, *argv, **kwarg):
        ret = []
        data = self._ifc.run()
        parsed = self._ifc.parse(data)
        for name, specs in parsed['addrs'].items():
            for spec in specs:
                msg = ifaddrmsg().load(spec)
                del msg['value']
                ret.append(msg)
        return ret

    def get_neighbours(self, *argv, **kwarg):
        return []

    def get_routes(self, *argv, **kwarg):
        return []


class RawIPRoute(IPRoute):
    pass
