import os

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
    '''
    '''

    def __init__(self, *argv, **kwarg):
        self._ifc = Ifconfig()
        self.marshal = MarshalRtnl()
        send_ns = Namespace(self, {'addr_pool': AddrPool(0x10000, 0x1ffff),
                                   'monitor': False})
        self._sproxy = NetlinkProxy(policy='return', nl=send_ns)
        self._fd = None
        self._pfdr, self._pfdw = os.pipe()
        self._outq = queue.Queue()

    def bind(self, *argv, **kwarg):
        self._rtm = RTMSocket()
        self._fd = self._rtm._sock.fileno()

    def fileno(self):
        return self._pfdr

    def recv(self, bufsize):
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
