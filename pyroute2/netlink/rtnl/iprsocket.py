import os
import sys

from pyroute2 import config
from pyroute2.netlink import NETLINK_ROUTE, rtnl
from pyroute2.netlink.nlsocket import AsyncNetlinkSocket, ChaoticNetlinkSocket
from pyroute2.netlink.proxy import NetlinkProxy
from pyroute2.netlink.rtnl.marshal import MarshalRtnl

if sys.platform.startswith('linux'):
    from pyroute2.netlink.rtnl.ifinfmsg.proxy import proxy_newlink
    from pyroute2.netlink.rtnl.probe_msg import proxy_newprobe


class IPRSocket(AsyncNetlinkSocket):
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

    def __init__(
        self,
        port=None,
        pid=None,
        fileno=None,
        sndbuf=1048576,
        rcvbuf=1048576,
        rcvsize=16384,
        all_ns=False,
        async_qsize=None,
        nlm_generator=None,
        target='localhost',
        ext_ack=False,
        strict_check=False,
        groups=0,
        nlm_echo=False,
        use_socket=None,
        netns=None,
        netns_path=None,
        flags=os.O_CREAT,
        libc=None,
    ):
        self.marshal = MarshalRtnl()
        super().__init__(
            family=NETLINK_ROUTE,
            port=port,
            pid=pid,
            fileno=fileno,
            sndbuf=sndbuf,
            rcvbuf=rcvbuf,
            rcvsize=rcvsize,
            all_ns=all_ns,
            async_qsize=async_qsize,
            nlm_generator=nlm_generator,
            target=target,
            ext_ack=ext_ack,
            strict_check=strict_check,
            groups=groups,
            nlm_echo=nlm_echo,
            use_socket=use_socket,
            netns=netns,
            flags=flags,
            libc=libc,
        )
        if sys.platform.startswith('linux'):
            self.request_proxy = NetlinkProxy(
                pmap={
                    rtnl.RTM_NEWLINK: proxy_newlink,
                    rtnl.RTM_NEWPROBE: proxy_newprobe,
                },
                netns=netns,
            )
        if self.spec['groups'] == 0:
            self.spec['groups'] = rtnl.RTMGRP_DEFAULTS
        self.spec['netns_path'] = netns_path or config.netns_path

    async def bind(self, groups=None, **kwarg):
        return await super().bind(
            groups if groups is not None else self.status['groups'], **kwarg
        )


class ChaoticIPRSocket(IPRSocket, ChaoticNetlinkSocket):
    pass
