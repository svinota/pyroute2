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
        'host_name': 'TFY-LX1',
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
        'vendor_id': 'android-dhcp-13',
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
        'host_name': 'Wii',
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
        'host_name': 'LG_Smart_Laundry2_open',
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
        'host_name': 'Netatmo-Personal-Weather-Station',
    }


def test_invalid_router_option(
    pcap: PcapFile, caplog: pytest.LogCaptureFixture
):
    '''Last opt. has an invalid length; the rest of the packet is decoded.'''
    caplog.set_level('ERROR', logger='pyroute2.dhcp')
    ack = parse_pcap(pcap, 1)[0]
    assert caplog.messages == [
        'Cannot decode option 3 as string: '
        'unpack requires a buffer of 255 bytes'
    ]
    assert ack.dhcp['options'] == {
        'broadcast_address': '192.168.42.255',
        'domain_name': 'toulouse.fourcot.fr',
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


def test_android_tethering_renew(pcap: PcapFile):
    '''Renew process for a Debian pc connected to an Android phone.'''
    client_mac = 'a0:a4:c5:93:ac:60'
    client_ip = '192.168.72.168'
    request, ack = parse_pcap(pcap, expected_packets=2)
    assert request.message_type == dhcp.MessageType.REQUEST
    assert request.eth_src == request.dhcp['chaddr'] == client_mac
    assert request.ip_src == request.dhcp['ciaddr'] == client_ip
    assert request.dhcp['secs'] == 1
    assert request.dhcp['options'] == {
        'client_id': {'key': 'a0:a4:c5:93:ac:60', 'type': 1},
        'host_name': 'thinkpad-eno',
        'max_msg_size': 0xFFFF,
        'message_type': dhcp.MessageType.REQUEST,
        'parameter_list': [
            dhcp.Option.SUBNET_MASK,
            dhcp.Option.TIME_OFFSET,
            dhcp.Option.NAME_SERVER,
            dhcp.Option.HOST_NAME,
            dhcp.Option.DOMAIN_NAME,
            dhcp.Option.INTERFACE_MTU,
            dhcp.Option.BROADCAST_ADDRESS,
            dhcp.Option.CLASSLESS_STATIC_ROUTE,
            dhcp.Option.ROUTER,
            dhcp.Option.STATIC_ROUTE,
            dhcp.Option.NIS_DOMAIN,
            dhcp.Option.NIS_SERVERS,
            dhcp.Option.NTP_SERVERS,
            dhcp.Option.DOMAIN_SEARCH,
            dhcp.Option.PRIVATE_CLASSIC_ROUTE_MS,
            dhcp.Option.PRIVATE_PROXY_AUTODISCOVERY,
            dhcp.Option.ROOT_PATH,
        ],
    }

    assert ack.message_type == dhcp.MessageType.ACK
    assert ack.eth_dst == ack.dhcp['chaddr'] == client_mac
    assert ack.ip_dst == ack.dhcp['ciaddr'] == client_ip
    assert ack.dhcp['options'] == {
        'broadcast_address': '192.168.72.255',
        'host_name': 'thinkpad-eno',
        'lease_time': 3599,
        'message_type': dhcp.MessageType.ACK,
        'name_server': ['192.168.72.238'],
        'rebinding_time': 3149,
        'renewal_time': 1799,
        'router': ['192.168.72.238'],
        'server_id': '192.168.72.238',
        'subnet_mask': '255.255.255.0',
        'vendor_specific_information': 'ANDROID_METERED',
    }


def test_huawei_discover_option_148(pcap: PcapFile):
    '''A DHCP offer with a non-standard option 148.'''
    discover, offer = parse_pcap(pcap, expected_packets=2)
    assert discover.message_type == dhcp.MessageType.DISCOVER
    assert discover.eth_src == 'a4:7c:c9:aa:20:20'
    assert discover.eth_dst == 'ff:ff:ff:ff:ff:ff'
    assert discover.ip_src == '0.0.0.0'
    assert discover.ip_dst == '255.255.255.255'
    assert discover.dhcp['flags'] == bootp.Flag.UNICAST
    assert discover.dhcp['options'] == {
        'client_id': {'key': 'a4:7c:c9:aa:20:20', 'type': 1},
        'max_msg_size': 1464,
        'message_type': dhcp.MessageType.DISCOVER,
        'parameter_list': [
            dhcp.Option.SUBNET_MASK,
            dhcp.Option.ROUTER,
            dhcp.Option.NAME_SERVER,
            dhcp.Option.DOMAIN_NAME,
            dhcp.Option.BROADCAST_ADDRESS,
            dhcp.Option.STATIC_ROUTE,
            dhcp.Option.VENDOR_SPECIFIC_INFORMATION,
            dhcp.Option.NETBIOS_NAME_SERVER,
            dhcp.Option.CLASSLESS_STATIC_ROUTE,
            dhcp.Option.DOTS_ADDR,
            184,  # this option is not assigned, Huawei calls it "option184"...
        ],
        'vendor_id': 'huawei AirEngine5761-11',
    }

    assert offer.message_type == dhcp.MessageType.OFFER
    assert offer.eth_src == 'b0:41:6f:06:26:14'
    assert offer.eth_dst == 'a4:7c:c9:aa:20:20'
    assert offer.ip_src == '10.184.16.1'
    # since the ap made an unicast DISCOVER, the offer is unicast
    assert offer.ip_dst == '10.184.27.103'
    assert offer.dhcp['options'] == {
        'broadcast_address': '10.184.31.255',
        # FIXME: this is not the correct format for the DOTS_ADDR option,
        # which is defined in RFC 8973.
        # If we implemented a parser for this option, it would crash and skip
        # the huawei value, which we don't want either...
        'dots_addr': list(
            b'agilemode=agile-cloud;'
            b'agilemanage-mode=ip;'
            b'agilemanage-domain=48.194.254.137;'
            b'agilemanage-port=10021;'
        ),
        'lease_time': 604800,
        'message_type': dhcp.MessageType.OFFER,
        'name_server': ['10.184.16.1'],
        'rebinding_time': 529200,
        'renewal_time': 302400,
        'router': ['10.184.16.1'],
        'server_id': '10.184.16.1',
        'subnet_mask': '255.255.240.0',
    }
