import errno
import queue
import struct

from pyroute2.lab import LAB_API
from pyroute2.netlink import nlmsg
from pyroute2.netlink.nlsocket import Stats
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.rtmsg import rtmsg


class MockLink:
    def __init__(
        self,
        index,
        ifname,
        address,
        broadcast='ff:ff:ff:ff:ff:ff',
        perm_address=None,
        flags=1,
        rx_bytes=0,
        tx_bytes=0,
        rx_packets=0,
        tx_packets=0,
        mtu=0,
        qdisc='noqueue',
    ):
        self.index = index
        self.ifname = ifname
        self.flags = flags
        self.address = address
        self.broadcast = broadcast
        self.perm_address = perm_address
        self.rx_bytes = rx_bytes
        self.tx_bytes = tx_bytes
        self.rx_packets = rx_packets
        self.tx_packets = tx_packets
        self.mtu = mtu
        self.qdisc = qdisc

    def export(self):
        return {
            'attrs': [
                ['IFLA_IFNAME', self.ifname],
                ['IFLA_TXQLEN', 1000],
                ['IFLA_OPERSTATE', 'UNKNOWN'],
                ['IFLA_LINKMODE', 0],
                ['IFLA_MTU', self.mtu],
                ['IFLA_GROUP', 0],
                ['IFLA_PROMISCUITY', 0],
                ['IFLA_NUM_TX_QUEUES', 1],
                ['IFLA_GSO_MAX_SEGS', 65535],
                ['IFLA_GSO_MAX_SIZE', 65536],
                ['IFLA_GRO_MAX_SIZE', 65536],
                ['IFLA_NUM_RX_QUEUES', 1],
                ['IFLA_CARRIER', 1],
                ['IFLA_QDISC', self.qdisc],
                ['IFLA_CARRIER_CHANGES', 0],
                ['IFLA_CARRIER_UP_COUNT', 0],
                ['IFLA_CARRIER_DOWN_COUNT', 0],
                ['IFLA_PROTO_DOWN', 0],
                [
                    'IFLA_MAP',
                    {
                        'base_addr': 0,
                        'dma': 0,
                        'irq': 0,
                        'mem_end': 0,
                        'mem_start': 0,
                        'port': 0,
                    },
                ],
                ['IFLA_ADDRESS', self.address],
                ['IFLA_BROADCAST', self.broadcast],
                [
                    'IFLA_STATS64',
                    {
                        'collisions': 0,
                        'multicast': 0,
                        'rx_bytes': self.rx_bytes,
                        'rx_compressed': 0,
                        'rx_crc_errors': 0,
                        'rx_dropped': 0,
                        'rx_errors': 0,
                        'rx_fifo_errors': 0,
                        'rx_frame_errors': 0,
                        'rx_length_errors': 0,
                        'rx_missed_errors': 0,
                        'rx_over_errors': 0,
                        'rx_packets': self.rx_packets,
                        'tx_aborted_errors': 0,
                        'tx_bytes': self.tx_bytes,
                        'tx_carrier_errors': 0,
                        'tx_compressed': 0,
                        'tx_dropped': 0,
                        'tx_errors': 0,
                        'tx_fifo_errors': 0,
                        'tx_heartbeat_errors': 0,
                        'tx_packets': self.tx_packets,
                        'tx_window_errors': 0,
                    },
                ],
                [
                    'IFLA_STATS',
                    {
                        'collisions': 0,
                        'multicast': 0,
                        'rx_bytes': self.rx_bytes,
                        'rx_compressed': 0,
                        'rx_crc_errors': 0,
                        'rx_dropped': 0,
                        'rx_errors': 0,
                        'rx_fifo_errors': 0,
                        'rx_frame_errors': 0,
                        'rx_length_errors': 0,
                        'rx_missed_errors': 0,
                        'rx_over_errors': 0,
                        'rx_packets': self.rx_packets,
                        'tx_aborted_errors': 0,
                        'tx_bytes': self.tx_bytes,
                        'tx_carrier_errors': 0,
                        'tx_compressed': 0,
                        'tx_dropped': 0,
                        'tx_errors': 0,
                        'tx_fifo_errors': 0,
                        'tx_heartbeat_errors': 0,
                        'tx_packets': self.tx_packets,
                        'tx_window_errors': 0,
                    },
                ],
                ['IFLA_XDP', {'attrs': [['IFLA_XDP_ATTACHED', None]]}],
                (
                    'IFLA_PERM_ADDRESS',
                    self.perm_address if self.perm_address else self.address,
                ),
                [
                    'IFLA_AF_SPEC',
                    {
                        'attrs': [
                            [
                                'AF_INET',
                                {
                                    'accept_local': 0,
                                    'accept_redirects': 1,
                                    'accept_source_route': 0,
                                    'arp_accept': 0,
                                    'arp_announce': 0,
                                    'arp_ignore': 0,
                                    'arp_notify': 0,
                                    'arpfilter': 0,
                                    'bootp_relay': 0,
                                    'dummy': 65672,
                                    'force_igmp_version': 0,
                                    'forwarding': 1,
                                    'log_martians': 0,
                                    'mc_forwarding': 0,
                                    'medium_id': 0,
                                    'nopolicy': 1,
                                    'noxfrm': 1,
                                    'promote_secondaries': 1,
                                    'proxy_arp': 0,
                                    'proxy_arp_pvlan': 0,
                                    'route_localnet': 0,
                                    'rp_filter': 2,
                                    'secure_redirects': 1,
                                    'send_redirects': 1,
                                    'shared_media': 1,
                                    'src_vmark': 0,
                                    'tag': 0,
                                },
                            ]
                        ]
                    },
                ],
            ],
            'change': 0,
            'event': 'RTM_NEWLINK',
            'family': 0,
            'flags': self.flags,
            'header': {
                'error': None,
                'flags': 2,
                'length': 1364,
                'pid': 303471,
                'sequence_number': 260,
                'stats': Stats(qsize=0, delta=0, delay=0),
                'target': 'localhost',
                'type': 16,
            },
            'ifi_type': 772,
            'index': self.index,
            'state': 'up' if self.flags & 1 else 'down',
        }


class MockAddress:
    def __init__(
        self, index, label, address, broadcast, prefixlen, family=2, local=None
    ):
        self.address = address
        self.local = local
        self.broadcast = broadcast
        self.prefixlen = prefixlen
        self.index = index
        self.label = label
        self.family = family

    def export(self):
        return {
            'family': self.family,
            'prefixlen': self.prefixlen,
            'flags': 0,
            'scope': 0,
            'index': self.index,
            'attrs': [
                ('IFA_ADDRESS', self.address),
                ('IFA_LOCAL', self.local if self.local else self.address),
                ('IFA_BROADCAST', self.broadcast),
                ('IFA_LABEL', self.label),
                ('IFA_FLAGS', 512),
                (
                    'IFA_CACHEINFO',
                    {
                        'ifa_preferred': 3476,
                        'ifa_valid': 3476,
                        'cstamp': 138655779,
                        'tstamp': 141288674,
                    },
                ),
            ],
            'header': {
                'length': 88,
                'type': 20,
                'flags': 2,
                'sequence_number': 256,
                'pid': 320994,
                'error': None,
                'target': 'localhost',
                'stats': Stats(qsize=0, delta=0, delay=0),
            },
            'event': 'RTM_NEWADDR',
        }


class MockRoute:
    def __init__(
        self,
        dst,
        oif,
        gateway=None,
        prefsrc=None,
        family=2,
        dst_len=24,
        table=254,
        scope=253,
        proto=2,
        route_type=1,
    ):
        self.dst = dst
        self.gateway = gateway
        self.prefsrc = prefsrc
        self.oif = oif
        self.family = family
        self.dst_len = dst_len
        self.table = table
        self.scope = scope
        self.proto = proto
        self.route_type = route_type

    def export(self):
        ret = {
            'family': self.family,
            'dst_len': self.dst_len,
            'src_len': 0,
            'tos': 0,
            'table': self.table,
            'proto': self.proto,
            'scope': self.scope,
            'type': 2,
            'flags': 0,
            'attrs': [('RTA_TABLE', self.table), ('RTA_OIF', self.oif)],
            'header': {
                'length': 60,
                'type': 24,
                'flags': 2,
                'sequence_number': 255,
                'pid': 325359,
                'error': None,
                'target': 'localhost',
                'stats': Stats(qsize=0, delta=0, delay=0),
            },
            'event': 'RTM_NEWROUTE',
        }
        if self.dst is not None:
            ret['attrs'].append(('RTA_DST', self.dst))
        if self.prefsrc is not None:
            ret['attrs'].append(('RTA_PREFSRC', self.prefsrc))
        if self.gateway is not None:
            ret['attrs'].append(('RTA_GATEWAY', self.gateway))
        return ret


REGISTRY_LINKS = [
    MockLink(
        index=1,
        ifname='lo',
        address='00:00:00:00:00:00',
        broadcast='00:00:00:00:00:00',
        rx_bytes=43309665,
        tx_bytes=43309665,
        rx_packets=173776,
        tx_packets=173776,
        mtu=65536,
        qdisc='noqueue',
    ),
    MockLink(
        index=2,
        ifname='eth0',
        address='52:54:00:72:58:b2',
        broadcast='ff:ff:ff:ff:ff:ff',
        rx_bytes=175340,
        tx_bytes=175340,
        rx_packets=10251,
        tx_packets=10251,
        mtu=1500,
        qdisc='fq_codel',
    ),
]

REGISTRY_ADDRS = [
    MockAddress(
        index=1,
        label='lo',
        address='127.0.0.1',
        broadcast='127.255.255.255',
        prefixlen=8,
    ),
    MockAddress(
        index=2,
        label='eth0',
        address='192.168.122.28',
        broadcast='192.168.122.255',
        prefixlen=24,
    ),
]

REGISTRY_ROUTES = [
    MockRoute(
        dst=None, gateway='192.168.122.1', oif=2, dst_len=0, table=254, scope=0
    ),
    MockRoute(dst='192.168.122.0', oif=2, dst_len=24, table=254),
    MockRoute(dst='127.0.0.0', oif=1, dst_len=8, table=255, route_type=2),
    MockRoute(dst='127.0.0.1', oif=1, dst_len=32, table=255, route_type=2),
    MockRoute(
        dst='127.255.255.255', oif=1, dst_len=32, table=255, route_type=3
    ),
    MockRoute(
        dst='192.168.122.28', oif=2, dst_len=32, table=255, route_type=2
    ),
    MockRoute(
        dst='192.168.122.255', oif=2, dst_len=32, table=255, route_type=3
    ),
]


class IPRoute(LAB_API):
    def __init__(self, *argv, **kwarg):
        super().__init__()
        self.target = kwarg.get('target')
        self.output_queue = queue.Queue(maxsize=512)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self, code=errno.ECONNRESET):
        self.output_queue.put(struct.pack('IHHQIQQ', 28, 2, 0, 0, code, 0, 0))

    def bind(self, async_cache=True, clone_socket=True):
        pass

    def dump(self):
        for method in (self.get_links, self.get_addr, self.get_routes):
            for msg in method():
                yield msg

    def _get_dump(self, dump, msg_class):
        for data in dump:
            loader = msg_class()
            loader.load(data.export())
            loader.encode()
            msg = msg_class()
            msg.data = loader.data
            msg.decode()
            if self.target is not None:
                msg['header']['target'] = self.target
            yield msg

    def get(self):
        msg = nlmsg()
        msg.data = self.output_queue.get()
        msg.decode()
        msg['header']['error'] = None
        if self.target is not None:
            msg['header']['target'] = self.target
        return (msg,)

    def get_addr(self):
        return self._get_dump(REGISTRY_ADDRS, ifaddrmsg)

    def get_links(self):
        return self._get_dump(REGISTRY_LINKS, ifinfmsg)

    def get_routes(self):
        return self._get_dump(REGISTRY_ROUTES, rtmsg)


class ChaoticIPRoute:
    def __init__(self, *argv, **kwarg):
        raise NotImplementedError()


class RawIPRoute:
    def __init__(self, *argv, **kwarg):
        raise NotImplementedError()
