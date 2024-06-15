import sys

from pyroute2.common import AddrPool, Namespace
from pyroute2.netlink import NETLINK_ROUTE, rtnl
from pyroute2.netlink.nlsocket import (
    BatchSocket,
    ChaoticNetlinkSocket,
    NetlinkSocket,
)
from pyroute2.netlink.proxy import NetlinkProxy
from pyroute2.netlink.rtnl.marshal import MarshalRtnl

if sys.platform.startswith('linux'):
    from pyroute2.netlink.rtnl.ifinfmsg.proxy import (
        proxy_newlink,
        proxy_setlink,
    )
    from pyroute2.netlink.rtnl.probe_msg import proxy_newprobe


class IPRSocket(NetlinkSocket):
    '''
    The simplest class, that connects together the netlink parser and
    a generic Python socket implementation. Provides method get() to
    receive the next message from netlink socket and parse it. It is
    just simple socket-like class, it implements no buffering or
    like that. It spawns no additional threads, leaving this up to
    developers.

    Please note, that netlink is an asynchronous protocol with
    non-guaranteed delivery. You should be fast enough to get all the
    messages in time. If the message flow rate is higher than the
    speed you parse them with, exceeding messages will be dropped.

    *Usage*

    Threadless RT netlink monitoring with blocking I/O calls:

        >>> from pyroute2 import IPRSocket
        >>> from pprint import pprint
        >>> s = IPRSocket()
        >>> s.bind()
        >>> pprint(s.get())
        [{'attrs': [('RTA_TABLE', 254),
                    ('RTA_DST', '2a00:1450:4009:808::1002'),
                    ('RTA_GATEWAY', 'fe80:52:0:2282::1fe'),
                    ('RTA_OIF', 2),
                    ('RTA_PRIORITY', 0),
                    ('RTA_CACHEINFO', {'rta_clntref': 0,
                                       'rta_error': 0,
                                       'rta_expires': 0,
                                       'rta_id': 0,
                                       'rta_lastuse': 5926,
                                       'rta_ts': 0,
                                       'rta_tsage': 0,
                                       'rta_used': 1})],
          'dst_len': 128,
          'event': 'RTM_DELROUTE',
          'family': 10,
          'flags': 512,
          'header': {'error': None,
                     'flags': 0,
                     'length': 128,
                     'pid': 0,
                     'sequence_number': 0,
                     'type': 25},
          'proto': 9,
          'scope': 0,
          'src_len': 0,
          'table': 254,
          'tos': 0,
          'type': 1}]
        >>>
    '''

    def __init__(self, *argv, **kwarg):
        if 'family' in kwarg:
            kwarg.pop('family')
        super().__init__(NETLINK_ROUTE, *argv[1:], **kwarg)
        self.marshal = MarshalRtnl()
        if self.status['groups'] == 0:
            self.spec['groups'] = rtnl.RTMGRP_DEFAULTS
        self._s_channel = None
        if sys.platform.startswith('linux'):
            send_ns = Namespace(
                self,
                {'addr_pool': AddrPool(0x10000, 0x1FFFF), 'monitor': False},
            )
            self._sproxy = NetlinkProxy(policy='return', nl=send_ns)
            self._sproxy.pmap = {
                rtnl.RTM_NEWLINK: proxy_newlink,
                rtnl.RTM_SETLINK: proxy_setlink,
                rtnl.RTM_NEWPROBE: proxy_newprobe,
            }

    def bind(self, groups=None, **kwarg):
        super().bind(
            groups if groups is not None else self.status['groups'], **kwarg
        )

    def sendto_gate(self, msg, addr):
        msg.reset()
        msg.encode()
        if self.compiled is not None:
            return self.compiled.append(msg.data)
        ret = self._sproxy.handle(msg)
        if ret is not None:
            if ret['verdict'] == 'forward':
                return self._sendto(ret['data'], addr)
            elif ret['verdict'] in ('return', 'error'):
                if self._s_channel is not None:
                    return self._s_channel.send(ret['data'])
                else:
                    msgs = self.marshal.parse(ret['data'])
                    for msg in msgs:
                        seq = msg['header']['sequence_number']
                        if seq in self.backlog:
                            self.backlog[seq].append(msg)
                        else:
                            self.backlog[seq] = [msg]
                    return len(ret['data'])
            else:
                ValueError('Incorrect verdict')

        return self._sendto(msg.data, addr)


class IPBatchSocket(IPRSocket, BatchSocket):
    pass


class ChaoticIPRSocket(IPRSocket, ChaoticNetlinkSocket):
    pass
