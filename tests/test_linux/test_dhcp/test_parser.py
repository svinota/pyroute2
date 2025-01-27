from fixtures.pcap_files import PcapFile

from pyroute2.dhcp.dhcp4socket import AsyncDHCP4Socket
from pyroute2.dhcp.enums import bootp, dhcp


def test_decode_simple_lease_process(pcap: PcapFile):
    '''Decode a simple DHCP handshake using AsyncDHCP4Socket.'''
    decoded_dhcp_messages = [AsyncDHCP4Socket._decode_msg(i) for i in pcap]
    assert len(decoded_dhcp_messages) == 4
    discover, offer, request, ack = decoded_dhcp_messages

    assert discover.message_type == dhcp.MessageType.DISCOVER
    assert discover.dhcp['flags'] == bootp.Flag.BROADCAST
    assert discover.sport, discover.dport == (68, 67)
    assert discover.dhcp['options']['lease_time'] == 0xFFFFFFFF  # infinity
    assert discover.dhcp['options']['parameter_list'] == [
        dhcp.Parameter.SUBNET_MASK,
        dhcp.Parameter.ROUTER,
        dhcp.Parameter.DOMAIN_NAME_SERVER,
        dhcp.Parameter.DOMAIN_NAME,
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
    decoded_dhcp_messages = [AsyncDHCP4Socket._decode_msg(i) for i in pcap]
    assert len(decoded_dhcp_messages) == 1
    request = decoded_dhcp_messages[0]
    assert request.message_type == dhcp.MessageType.REQUEST
    assert request.dhcp['op'] == bootp.MessageType.BOOTREQUEST
    assert request.dhcp['chaddr'] == client_mac
    assert request.dhcp['flags'] == bootp.Flag.UNICAST
    assert request.dhcp['options'] == {
        'client_id': {
            'key': client_mac,
            'type': 1,  # TODO use constant/enum ?
        },
        'host_name': b'TFY-LX',
        'max_msg_size': 1500,
        'message_type': dhcp.MessageType.REQUEST,
        'parameter_list': [
            dhcp.Option.SUBNET_MASK,
            dhcp.Option.ROUTER,
            dhcp.Option.NAME_SERVER,
            dhcp.Option.DOMAIN_NAME,
            26,  # FIXME wait for Brian's branch
            dhcp.Option.BROADCAST_ADDRESS,
            # TODO: we should ask for these three too
            dhcp.Option.LEASE_TIME,
            dhcp.Option.RENEWAL_TIME,
            dhcp.Option.REBINDING_TIME,
            dhcp.Option.VENDOR_SPECIFIC_INFORMATION,
            114,  # TODO dhcp captive portal
            108,  # TODO ipv6 only preferred
        ],
        'requested_ip': '192.168.94.191',
        'vendor_id': b'android-dhcp-1',
    }
    assert request.eth_src == client_mac
    assert request.eth_dst == 'ff:ff:ff:ff:ff:ff'
    assert request.ip_src == '0.0.0.0'
    assert (request.sport, request.dport) == (68, 67)
