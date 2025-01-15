'''
IPv4 DHCP socket
================

'''

import asyncio
import logging
import socket

from pyroute2.common import AddrPool
from pyroute2.compat import ETHERTYPE_IP
from pyroute2.dhcp.dhcp4msg import dhcp4msg
from pyroute2.ext.rawsocket import AsyncRawSocket
from pyroute2.protocols import ethmsg, ip4msg, udp4_pseudo_header, udpmsg

LOG = logging.getLogger(__name__)

UDP_HEADER_SIZE = 8
IPV4_HEADER_SIZE = 20


def listen_udp_port(port: int = 68) -> list[list[int]]:
    # pre-scripted BPF code that matches UDP port
    bpf_code = [
        [40, 0, 0, 12],
        [21, 0, 8, 2048],
        [48, 0, 0, 23],
        [21, 0, 6, 17],
        [40, 0, 0, 20],
        [69, 4, 0, 8191],
        [177, 0, 0, 14],
        [72, 0, 0, 16],
        [21, 0, 1, port],
        [6, 0, 0, 65535],
        [6, 0, 0, 0],
    ]
    return bpf_code


class AsyncDHCP4Socket(AsyncRawSocket):
    '''
    Parameters:

    * ifname -- interface name to work on

    This raw socket binds to an interface and installs BPF filter
    to get only its UDP port. It can be used in poll/select and
    provides also the context manager protocol, so can be used in
    `with` statements.

    It does not provide any DHCP state machine, and does not inspect
    DHCP packets, it is totally up to you. No default values are
    provided here, except `xid` -- DHCP transaction ID. If `xid` is
    not provided, DHCP4Socket generates it for outgoing messages.
    '''

    def __init__(self, ifname, port: int = 68):
        AsyncRawSocket.__init__(self, ifname, listen_udp_port(port))
        self.port = port
        # Create xid pool
        #
        # Every allocated xid will be released automatically after 1024
        # alloc() calls, there is no need to call free(). Minimal xid == 16
        self.xid_pool = AddrPool(
            minaddr=16, release=1024
        )  # TODO : maybe it should be in the client and not here ?
        self.aio_loop = asyncio.get_running_loop()

    async def put(
        self,
        msg: dhcp4msg,
        eth_dst: str = 'ff:ff:ff:ff:ff:ff',
        ip_dst: str = '255.255.255.255',
        dport: int = 67,
    ) -> dhcp4msg:
        '''
        Put DHCP message. Parameters:

        * msg -- dhcp4msg instance
        * eth_dst -- dest MAC address
        * ip_dst -- dest IP address
        * dport -- DHCP server port

        Examples::

            sock.put(dhcp4msg({'op': BOOTREQUEST,
                               'chaddr': 'ff:11:22:33:44:55',
                               'options': {'message_type': DHCPREQUEST,
                                           'parameter_list': [1, 3, 6, 12, 15],
                                           'requested_ip': '172.16.101.2',
                                           'server_id': '172.16.101.1'}}))

        The method returns the sent dhcp4msg, so one can get from
        there the `xid` (transaction id) and other details.
        '''
        # DHCP layer
        dhcp = msg

        # dhcp transaction id
        if dhcp['xid'] is None:
            dhcp['xid'] = self.xid_pool.alloc()

        # auto add src addr
        if dhcp['chaddr'] is None:
            dhcp['chaddr'] = self.l2addr

        data = dhcp.encode().buf
        dhcp_payload_size = len(data)

        # UDP layer
        udp = udpmsg(
            {
                'sport': self.port,
                'dport': dport,
                'len': UDP_HEADER_SIZE + dhcp_payload_size,
            }
        )
        # Pseudo UDP header, only for checksum purposes
        udph = udp4_pseudo_header(
            {'dst': ip_dst, 'len': UDP_HEADER_SIZE + dhcp_payload_size}
        )
        udp['csum'] = self.csum(udph.encode().buf + udp.encode().buf + data)
        udp.reset()

        # IPv4 layer
        ip4 = ip4msg(
            {
                'len': IPV4_HEADER_SIZE + UDP_HEADER_SIZE + dhcp_payload_size,
                'proto': socket.IPPROTO_UDP,
                'dst': ip_dst,
            }
        )
        ip4['csum'] = self.csum(ip4.encode().buf)
        ip4.reset()

        # MAC layer
        eth = ethmsg(
            {'dst': eth_dst, 'src': self.l2addr, 'type': ETHERTYPE_IP}
        )

        data = eth.encode().buf + ip4.encode().buf + udp.encode().buf + data
        await self.aio_loop.sock_sendall(self, data)
        dhcp.reset()
        return dhcp

    async def get(self) -> dhcp4msg:
        '''
        Get the next incoming packet from the socket and try
        to decode it as IPv4 DHCP. No analysis is done here,
        only MAC/IPv4/UDP headers are stripped out, and the
        rest is interpreted as DHCP.
        '''
        data = await self.aio_loop.sock_recv(self, 4096)
        eth = ethmsg(buf=data).decode()
        ip4 = ip4msg(buf=data, offset=eth.offset).decode()
        udp = udpmsg(buf=data, offset=ip4.offset).decode()
        return dhcp4msg(buf=data, offset=udp.offset).decode()
