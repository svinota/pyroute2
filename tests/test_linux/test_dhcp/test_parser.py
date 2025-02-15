from typing import Iterable

import pytest
from fixtures.pcap_files import PcapFile

from pyroute2.dhcp.dhcp4socket import AsyncDHCP4Socket
from pyroute2.dhcp.enums import bootp, dhcp
from pyroute2.dhcp.messages import ReceivedDHCPMessage


def parse_pcap(
    pcap: Iterable[bytes], expected_packets: int
) -> list[ReceivedDHCPMessage]:
    decoded_dhcp_messages = [AsyncDHCP4Socket._decode_msg(i) for i in pcap]
    assert len(decoded_dhcp_messages) == expected_packets
    return decoded_dhcp_messages


def test_decode_simple_lease_process(pcap: PcapFile):
    '''Decode a simple DHCP handshake using AsyncDHCP4Socket.'''
    discover, offer, request, ack = parse_pcap(pcap, expected_packets=4)
    assert discover.message_type == dhcp.MessageType.DISCOVER
    assert discover.dhcp['flags'] == bootp.Flag.BROADCAST
    assert discover.sport, discover.dport == (68, 67)
    assert discover.dhcp['options']['lease_time'] == -1  # infinity
    assert discover.dhcp['options']['parameter_list'] == [
        dhcp.Option.SUBNET_MASK,
        dhcp.Option.ROUTER,
        dhcp.Option.NAME_SERVER,
        dhcp.Option.DOMAIN_NAME,
    ]
    assert discover.dhcp['xid'] == 0x22334455
    assert offer.message_type == dhcp.MessageType.OFFER
    assert offer.dhcp['flags'] == bootp.Flag.BROADCAST
    assert offer.sport, offer.dport == (67, 68)
    assert offer.dhcp['xid'] == 0x22334455
    assert offer.dhcp['options']['lease_time'] == 43200
    assert offer.dhcp['options']['name_server'] == ['192.168.94.254']
    assert offer.dhcp['options']['router'] == ['192.168.94.254']
    assert offer.dhcp['options']['server_id'] == '192.168.94.254'
    assert offer.dhcp['options']['subnet_mask'] == '255.255.255.0'

    assert request.message_type == dhcp.MessageType.REQUEST
    assert request.dhcp['flags'] == bootp.Flag.BROADCAST
    assert request.sport, request.dport == (68, 67)
    assert request.dhcp['xid'] == 0x22334455

    assert ack.message_type == dhcp.MessageType.ACK
    assert ack.dhcp['flags'] == bootp.Flag.BROADCAST
    assert ack.sport, ack.dport == (67, 68)
    assert ack.dhcp['xid'] == 0x22334455
    assert ack.dhcp['options']['lease_time'] == 43200
    assert ack.dhcp['options']['name_server'] == ['192.168.94.254']
    assert ack.dhcp['options']['router'] == ['192.168.94.254']
    assert ack.dhcp['options']['server_id'] == '192.168.94.254'
    assert ack.dhcp['options']['subnet_mask'] == '255.255.255.0'


def test_android_reboot_request(pcap: PcapFile):
    '''Decode the request sent by an Android phone in init-reboot state.'''
    client_mac = '32:7a:80:aa:a7:c7'
    request = parse_pcap(pcap, expected_packets=1)[0]
    assert request.message_type == dhcp.MessageType.REQUEST
    assert request.dhcp['op'] == bootp.MessageType.BOOTREQUEST
    assert request.dhcp['chaddr'] == client_mac
    assert request.dhcp['flags'] == bootp.Flag.UNICAST
    assert request.dhcp['options'] == {
        'client_id': {
            'key': client_mac,
            'type': 1,  # TODO use constant/enum ?
        },
        'host_name': b'TFY-LX1',
        'max_msg_size': 1500,
        'message_type': dhcp.MessageType.REQUEST,
        'parameter_list': [
            dhcp.Option.SUBNET_MASK,
            dhcp.Option.ROUTER,
            dhcp.Option.NAME_SERVER,
            dhcp.Option.DOMAIN_NAME,
            dhcp.Option.INTERFACE_MTU,
            dhcp.Option.BROADCAST_ADDRESS,
            # TODO: we should ask for these three too
            dhcp.Option.LEASE_TIME,
            dhcp.Option.RENEWAL_TIME,
            dhcp.Option.REBINDING_TIME,
            dhcp.Option.VENDOR_SPECIFIC_INFORMATION,
            dhcp.Option.DHCP_CAPTIVE_PORTAL,
            dhcp.Option.IPV6_ONLY_PREFERRED,
        ],
        'requested_ip': '192.168.94.191',
        'vendor_id': b'android-dhcp-13',
    }
    assert request.eth_src == client_mac
    assert request.eth_dst == 'ff:ff:ff:ff:ff:ff'
    assert request.ip_src == '0.0.0.0'
    assert (request.sport, request.dport) == (68, 67)


def test_wii_discover(pcap: PcapFile):
    '''Decode the request sent by a Wii trying to get an address.'''
    client_mac = '00:1e:a9:87:91:a7'
    discover = parse_pcap(pcap, expected_packets=1)[0]
    assert discover.message_type == dhcp.MessageType.DISCOVER
    assert discover.dhcp['op'] == bootp.MessageType.BOOTREQUEST
    assert discover.dhcp['chaddr'] == client_mac
    assert discover.dhcp['flags'] == bootp.Flag.UNICAST
    assert discover.dhcp['options'] == {
        'client_id': {'key': client_mac, 'type': 1},
        'host_name': b'Wii',
        'message_type': dhcp.MessageType.DISCOVER,
        'parameter_list': [
            dhcp.Option.SUBNET_MASK,
            dhcp.Option.ROUTER,
            dhcp.Option.NAME_SERVER,
            dhcp.Option.DOMAIN_NAME,
            dhcp.Option.BROADCAST_ADDRESS,
            dhcp.Option.STATIC_ROUTE,
        ],
        'requested_ip': '192.168.94.147',
    }
    assert discover.eth_src == client_mac
    assert discover.eth_dst == 'ff:ff:ff:ff:ff:ff'
    assert discover.ip_src == '0.0.0.0'
    assert (discover.sport, discover.dport) == (68, 67)


def test_washing_machine_request(pcap: PcapFile):
    '''Decode a request sent by Quentin's "smart" (sic) washing machine.'''
    washing_mac = '14:7f:67:8a:7b:4a'
    request = parse_pcap(pcap, expected_packets=1)[0]
    assert request.message_type == dhcp.MessageType.REQUEST
    assert request.dhcp['op'] == bootp.MessageType.BOOTREQUEST
    assert request.dhcp['chaddr'] == washing_mac
    assert request.dhcp['flags'] == bootp.Flag.UNICAST
    assert request.dhcp['options'] == {
        'host_name': b'LG_Smart_Laundry2_open',
        'max_msg_size': 1500,
        'message_type': dhcp.MessageType.REQUEST,
        'parameter_list': [
            dhcp.Option.SUBNET_MASK,
            dhcp.Option.ROUTER,
            dhcp.Option.BROADCAST_ADDRESS,
            dhcp.Option.NAME_SERVER,
        ],
        'requested_ip': '192.168.0.33',
        'server_id': '192.168.0.254',
    }
    # despite being smart, this washing machine seems to invert the endianness
    # for the 'secs' field, so `00 01` (1s) becomes `01 00` (256s)
    assert request.dhcp['secs'] == 256
    assert request.eth_src == washing_mac
    assert request.eth_dst == 'ff:ff:ff:ff:ff:ff'
    assert request.ip_src == '0.0.0.0'
    assert (request.sport, request.dport) == (68, 67)


def test_netatmo_discover_request(pcap: PcapFile):
    disco1, disco2, request = parse_pcap(pcap, expected_packets=3)
    '''Packets from a netatmo weather station.

    it uses a embedded stack (lwip), so packets are minimalistic.
    '''
    # their source says:
    # we don't need the broadcast flag since we can receive unicast traffic
    # before being fully configured!
    assert (
        disco1.dhcp['flags']
        == disco2.dhcp['flags']
        == request.dhcp['flags']
        == bootp.Flag.UNICAST
    )

    # they do not seem to increment the `secs` field with time
    assert (
        disco1.dhcp['secs'] == disco2.dhcp['secs'] == request.dhcp['secs'] == 0
    )

    # they do not pass a client_id in options
    assert (
        disco1.dhcp['options']
        == disco2.dhcp['options']
        == {
            'message_type': dhcp.MessageType.DISCOVER,
            'max_msg_size': 1500,
            'parameter_list': [
                dhcp.Option.SUBNET_MASK,
                dhcp.Option.ROUTER,
                dhcp.Option.BROADCAST_ADDRESS,
                dhcp.Option.NAME_SERVER,
            ],
        }
    )
    assert request.dhcp['options'] == {
        'message_type': dhcp.MessageType.REQUEST,
        'max_msg_size': 1500,
        'requested_ip': '192.168.0.8',
        'server_id': '192.168.0.254',
        'parameter_list': [
            dhcp.Option.SUBNET_MASK,
            dhcp.Option.ROUTER,
            dhcp.Option.BROADCAST_ADDRESS,
            dhcp.Option.NAME_SERVER,
        ],
        'host_name': b'Netatmo-Personal-Weather-Station',
    }


def test_invalid_router_option(
    pcap: PcapFile, caplog: pytest.LogCaptureFixture
):
    '''Last opt. has an invalid length; the rest of the packet is decoded.'''
    caplog.set_level('ERROR', logger='pyroute2.dhcp')
    ack = parse_pcap(pcap, 1)[0]
    assert caplog.messages == [
        'Cannot decode option 0 as string: '
        'unpack requires a buffer of 255 bytes'
    ]
    assert ack.dhcp['options'] == {
        'broadcast_address': '192.168.42.255',
        'domain_name': b'toulouse.fourcot.fr',
        'lease_time': 604800,
        'message_type': dhcp.MessageType.ACK,
        'name_server': ['192.168.42.10'],
        'rebinding_time': 529200,
        'renewal_time': 302400,
        'server_id': '192.168.42.10',
        'subnet_mask': '255.255.255.0',
    }


def test_invalid_client_id_option(
    pcap: PcapFile, caplog: pytest.LogCaptureFixture
):
    '''The client id is declared as 8 bytes long instead of 7.'''
    caplog.set_level('ERROR', logger='pyroute2.dhcp')
    req = parse_pcap(pcap, 1)[0]
    # Options before the failed one are still decoded
    assert req.dhcp['options'] == {
        'max_msg_size': 1500,
        'message_type': dhcp.MessageType.REQUEST,
        'parameter_list': [
            dhcp.Option.SUBNET_MASK,
            dhcp.Option.CLASSLESS_STATIC_ROUTE,
            dhcp.Option.ROUTER,
            dhcp.Option.NAME_SERVER,
            dhcp.Option.DOMAIN_NAME,
            dhcp.Option.IPV6_ONLY_PREFERRED,
            dhcp.Option.DHCP_CAPTIVE_PORTAL,
            dhcp.Option.DOMAIN_SEARCH,
            dhcp.Option.PRIVATE_PROXY_AUTODISCOVERY,
            dhcp.Option.LDAP_SERVERS,
            dhcp.Option.NETBIOS_NAME_SERVER,
            dhcp.Option.NETBIOS_NODE_TYPE,
        ],
    }


@pytest.mark.parametrize(
    ('offset', 'err_msg'),
    (
        (
            0,
            'Cannot decode ethmsg dst: unpack_from requires a buffer '
            'of at least 6 bytes for unpacking 6 bytes at offset 0',
        ),
        (
            1,
            'Cannot decode ethmsg dst: unpack_from requires a buffer '
            'of at least 6 bytes for unpacking 6 bytes at offset 0',
        ),
        (
            8,
            'Cannot decode ethmsg src: unpack_from requires a buffer '
            'of at least 12 bytes for unpacking 6 bytes at offset 6',
        ),
        (
            20,
            'Cannot decode ip4msg flags: unpack_from requires a buffer '
            'of at least 22 bytes for unpacking 2 bytes at offset 20',
        ),
        (
            30,
            'Cannot decode ip4msg dst: unpack_from requires a buffer '
            'of at least 34 bytes for unpacking 4 bytes at offset 30',
        ),
        (
            40,
            'Cannot decode udpmsg csum: unpack_from requires a buffer '
            'of at least 42 bytes for unpacking 2 bytes at offset 40',
        ),
        (
            50,
            'Cannot decode dhcp4msg secs: unpack_from requires a buffer '
            'of at least 52 bytes for unpacking 2 bytes at offset 50',
        ),
        (
            60,
            'Cannot decode dhcp4msg yiaddr: unpack_from requires a buffer '
            'of at least 62 bytes for unpacking 4 bytes at offset 58',
        ),
        (
            70,
            'Cannot decode dhcp4msg chaddr: unpack_from requires a buffer '
            'of at least 86 bytes for unpacking 16 bytes at offset 70',
        ),
        (
            100,
            'Cannot decode dhcp4msg sname: unpack_from requires a buffer '
            'of at least 150 bytes for unpacking 64 bytes at offset 86',
        ),
        (
            200,
            'Cannot decode dhcp4msg file: unpack_from requires a buffer '
            'of at least 278 bytes for unpacking 128 bytes at offset 150',
        ),
        (
            280,
            'Cannot decode dhcp4msg cookie: unpack_from requires a buffer '
            'of at least 282 bytes for unpacking 4 bytes at offset 278',
        ),
    ),
)
def test_truncated_packet(pcap: PcapFile, offset: int, err_msg: str):
    '''Truncated packets raise ValueError when decoded.'''
    with pytest.raises(ValueError) as err_ctx:
        parse_pcap([i[:offset] for i in pcap], 1)[0]
    assert str(err_ctx.value) == err_msg + f' (actual buffer size is {offset})'
