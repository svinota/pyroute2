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
