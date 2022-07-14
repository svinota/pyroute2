import errno
import queue
import struct

from pyroute2.netlink.nlsocket import Stats
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg

DUMP_LINKS = [
    {
        'attrs': [
            ['IFLA_IFNAME', 'lo'],
            ['IFLA_TXQLEN', 1000],
            ['IFLA_OPERSTATE', 'UNKNOWN'],
            ['IFLA_LINKMODE', 0],
            ['IFLA_MTU', 65536],
            ['IFLA_MIN_MTU', 0],
            ['IFLA_MAX_MTU', 0],
            ['IFLA_GROUP', 0],
            ['IFLA_PROMISCUITY', 0],
            ['IFLA_NUM_TX_QUEUES', 1],
            ['IFLA_GSO_MAX_SEGS', 65535],
            ['IFLA_GSO_MAX_SIZE', 65536],
            ['IFLA_GRO_MAX_SIZE', 65536],
            ['IFLA_NUM_RX_QUEUES', 1],
            ['IFLA_CARRIER', 1],
            ['IFLA_QDISC', 'noqueue'],
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
            ['IFLA_ADDRESS', '00:00:00:00:00:00'],
            ['IFLA_BROADCAST', '00:00:00:00:00:00'],
            [
                'IFLA_STATS64',
                {
                    'collisions': 0,
                    'multicast': 0,
                    'rx_bytes': 43309665,
                    'rx_compressed': 0,
                    'rx_crc_errors': 0,
                    'rx_dropped': 0,
                    'rx_errors': 0,
                    'rx_fifo_errors': 0,
                    'rx_frame_errors': 0,
                    'rx_length_errors': 0,
                    'rx_missed_errors': 0,
                    'rx_over_errors': 0,
                    'rx_packets': 173776,
                    'tx_aborted_errors': 0,
                    'tx_bytes': 43309665,
                    'tx_carrier_errors': 0,
                    'tx_compressed': 0,
                    'tx_dropped': 0,
                    'tx_errors': 0,
                    'tx_fifo_errors': 0,
                    'tx_heartbeat_errors': 0,
                    'tx_packets': 173776,
                    'tx_window_errors': 0,
                },
            ],
            [
                'IFLA_STATS',
                {
                    'collisions': 0,
                    'multicast': 0,
                    'rx_bytes': 43309665,
                    'rx_compressed': 0,
                    'rx_crc_errors': 0,
                    'rx_dropped': 0,
                    'rx_errors': 0,
                    'rx_fifo_errors': 0,
                    'rx_frame_errors': 0,
                    'rx_length_errors': 0,
                    'rx_missed_errors': 0,
                    'rx_over_errors': 0,
                    'rx_packets': 173776,
                    'tx_aborted_errors': 0,
                    'tx_bytes': 43309665,
                    'tx_carrier_errors': 0,
                    'tx_compressed': 0,
                    'tx_dropped': 0,
                    'tx_errors': 0,
                    'tx_fifo_errors': 0,
                    'tx_heartbeat_errors': 0,
                    'tx_packets': 173776,
                    'tx_window_errors': 0,
                },
            ],
            ['IFLA_XDP', {'attrs': [['IFLA_XDP_ATTACHED', None]]}],
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
                                'igmpv2_unsolicited_report_interval': 10000,
                                'igmpv3_unsolicited_report_interval': 1000,
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
        'flags': 65609,
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
        'index': 1,
        'state': 'up',
    }
]

DUMP_ADDRS = [
    {
        'attrs': [
            ['IFA_ADDRESS', '127.0.0.1'],
            ['IFA_LOCAL', '127.0.0.1'],
            ['IFA_LABEL', 'lo'],
            ['IFA_FLAGS', 128],
            [
                'IFA_CACHEINFO',
                {
                    'cstamp': 155,
                    'ifa_preferred': 4294967295,
                    'ifa_valid': 4294967295,
                    'tstamp': 155,
                },
            ],
        ],
        'event': 'RTM_NEWADDR',
        'family': 2,
        'flags': 128,
        'header': {
            'error': None,
            'flags': 2,
            'length': 76,
            'pid': 303471,
            'sequence_number': 263,
            'stats': Stats(qsize=0, delta=0, delay=0),
            'target': 'localhost',
            'type': 20,
        },
        'index': 1,
        'prefixlen': 8,
        'scope': 254,
    }
]


class IPRoute:
    def __init__(self):
        self.output_queue = queue.Queue(maxsize=512)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self, code=errno.ECONNRESET):
        self.output_queue.put(struct.pack('IHHQIQQ', 28, 2, 0, 0, code, 0, 0))

    def dump(self):
        for method in (self.get_links, self.get_addr):
            for msg in method():
                yield msg

    def _get_dump(self, dump, msg_class):
        for data in dump:
            loader = msg_class()
            loader.load(data)
            loader.encode()
            msg = msg_class()
            msg.data = loader.data
            msg.decode()
            yield msg

    def get_addr(self):
        return self._get_dump(DUMP_ADDRS, ifaddrmsg)

    def get_links(self):
        return self._get_dump(DUMP_LINKS, ifinfmsg)


class ChaoticIPRoute:
    def __init__(self, *argv, **kwarg):
        raise NotImplementedError()


class RawIPRoute:
    def __init__(self, *argv, **kwarg):
        raise NotImplementedError()
