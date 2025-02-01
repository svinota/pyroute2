import os
import sys
from unittest import mock

from pyroute2 import config
from pyroute2.iproute.ipmock import IPEngine
from pyroute2.netlink import NETLINK_ROUTE, rtnl
from pyroute2.netlink.nlsocket import (
    AsyncNetlinkSocket,
    ChaoticNetlinkSocket,
    NetlinkSocket,
)
from pyroute2.netlink.proxy import NetlinkProxy
from pyroute2.netlink.rtnl.marshal import MarshalRtnl

if sys.platform.startswith('linux'):
    from pyroute2.netlink.rtnl.ifinfmsg.proxy import proxy_newlink
    from pyroute2.netlink.rtnl.probe_msg import proxy_newprobe


class AsyncIPRSocket(AsyncNetlinkSocket):
    '''A low-level class to provide RTNL socket.

    This is a low-level class designed to provide an RTNL
    asyncio-controlled socket. It does not include high-level
    methods like those found in AsyncIPRoute. Instead, it provides
    only common netlink methods such as `get()` and `put()`. For
    more details, refer to the `AsyncNetlinkSocket` documentation.

    ,, testcode::
        :hide:

        from pyroute2 import AsyncIPRSocket

        iprsock = AsyncIPRSocket()
        assert callable(iprsock.get)
        assert callable(iprsock.put)
        assert callable(iprsock.nlm_request)
        assert callable(iprsock.bind)

    Since the underlying socket is controlled by asyncio, it is
    not possible to use it in poll/select loops. If you want
    such API, consider using synchronous `IPRSocket`.

    .. warning::

        Netlink is an asynchronous protocol that does not guarantee
        message delivery order or even delivery itself.

    Your code must process incoming messages quickly enough to
    prevent the RCVBUF from overflowing. If the RCVBUF overflows,
    all subsequent socket operations will raise an OSError:

    .. code::

        >>> iprsock.get()
        Traceback (most recent call last):
          File "<python-input-12>", line 1, in <module>
            iprsock.get()
            ~~~~~~~~^^
          File ".../pyroute2/netlink/rtnl/iprsocket.py", line 276, in get
            data = self.socket.recv(16384)
        OSError: [Errno 105] No buffer space available
        >>>

    If this exception occurs, the only solution is to close the
    socket and create a new one.

    This class does not handle protocol-level error propagation; it
    only provides socket-level error handling. It is the user's
    responsibility to catch and manage protocol-level errors:

    .. testsetup:: as0

        from pyroute2.netlink import nlmsgerr, NLMSG_ERROR
        msg = nlmsgerr()
        msg['header']['type'] = NLMSG_ERROR
        msg['error'] = 42
        msg.reset()
        msg.encode()
        msg.decode()

    .. testcode:: as0

        if msg.get(('header', 'type')) == NLMSG_ERROR:
            # prints error code and the request that
            # triggered the error
            print(
                msg.get('error'),
                msg.get('msg'),
            )

    .. testoutput:: as0
        :hide:

        42 None


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
        if config.mock_netlink:
            use_socket = IPEngine()
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


class NotLocal:
    event_loop = None
    socket = None
    fileno = None
    msg_queue = mock.Mock()


class IPRSocket(NetlinkSocket):
    '''Synchronous select-compatible netlink socket.

    `IPRSocket` is the synchronous counterpart to `AsyncIPRSocket`.
    A key feature of `IPRSocket` is that the underlying netlink
    socket operates out of asyncio control, allowing it to be
    used in poll/select loops.

    .. testcode::

        import select

        from pyroute2 import IPRSocket
        from pyroute2.netlink import NLM_F_DUMP, NLM_F_REQUEST
        from pyroute2.netlink.rtnl import RTM_GETLINK
        from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg

        with IPRSocket() as iprsock:
            iprsock.put(
                ifinfmsg(),
                msg_type=RTM_GETLINK,
                msg_flags=NLM_F_REQUEST | NLM_F_DUMP
            )

            ret = []

            while True:
                rl, wl, xl = select.select([iprsock], [], [], 0)
                if not len(rl):
                    break
                ret.extend(iprsock.get())

            for link in ret:
                if link.get('event') == 'RTM_NEWLINK':
                    print(
                        link.get('ifname'),
                        link.get('state'),
                        link.get('address'),
                    )

    .. testoutput::

        lo up 00:00:00:00:00:00
        eth0 up 52:54:00:72:58:b2

    Threadless RT netlink monitoring with blocking I/O calls:

        >>> from pyroute2 import IPRSocket
        >>> from pprint import pprint
        >>> s = IPRSocket()
        >>> s.bind()
        >>> pprint(s.get())
        [{'attrs': [('RTA_TABLE', 254),
                    ('RTA_OIF', 2),
                    ('RTA_GATEWAY', '192.168.122.1')],
          'dst_len': 0,
          'event': 'RTM_NEWROUTE',
          'family': 2,
          'flags': 0,
          'header': {'error': None,
                     'flags': 2,
                     'length': 52,
                     'pid': 325359,
                     'sequence_number': 255,
                     'type': 24},
          'proto': 2,
          'scope': 0,
          'src_len': 0,
          'table': 254,
          'tos': 0,
          'type': 2}]
        >>>

    Like `AsyncIPRSocket`, it does not perform response reassembly,
    protocol-level error propagation, or packet buffering.
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
        self.asyncore = AsyncIPRSocket(
            port,
            pid,
            fileno,
            sndbuf,
            rcvbuf,
            rcvsize,
            all_ns,
            async_qsize,
            nlm_generator,
            target,
            ext_ack,
            strict_check,
            groups,
            nlm_echo,
            use_socket,
            netns,
            netns_path,
            flags,
            libc,
        )
        self.asyncore.local = NotLocal()
        self.asyncore.local.event_loop = self.asyncore.setup_event_loop()
        self.asyncore.local.socket = self.asyncore.setup_socket()

    @property
    def socket(self):
        return self.asyncore.local.socket

    @property
    def fileno(self):
        return self.asyncore.local.socket.fileno

    def get(self, msg_seq=0, terminate=None, callback=None, noraise=False):
        data = self.socket.recv(16384)
        return [x for x in self.marshal.parse(data)]


class ChaoticIPRSocket(AsyncIPRSocket, ChaoticNetlinkSocket):
    pass
