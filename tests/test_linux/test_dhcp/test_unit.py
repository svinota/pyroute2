import pytest
from fixtures.dhcp_servers.mock import MockDHCPServerFixture
from fixtures.interfaces import VethPair

from pyroute2.dhcp.client import AsyncDHCPClient, ClientConfig
from pyroute2.dhcp.enums import bootp, dhcp
from pyroute2.dhcp.fsm import State


@pytest.mark.asyncio
async def test_get_and_renew_lease(
    mock_dhcp_server: MockDHCPServerFixture,
    veth_pair: VethPair,
    caplog: pytest.LogCaptureFixture,
):
    '''A lease is obtained with a 1s renewing time, the client renews it.

    The test pcap file contains the OFFER & the 2 ACKs.
    '''
    caplog.set_level("DEBUG")
    # FIXME the test will probably break if we randomize xids (and we should)
    cfg = ClientConfig(interface=veth_pair.client, xid=0x10)
    async with AsyncDHCPClient(cfg) as cli:
        await cli.bootstrap()
        await cli.wait_for_state(State.SELECTING, timeout=1)
        # server sends an OFFER
        await cli.wait_for_state(State.REQUESTING, timeout=1)
        # server sends an ACK
        await cli.wait_for_state(State.BOUND, timeout=1)
        # the ACK in the pcap was modified to set a renewing time of 1s
        await cli.wait_for_state(State.RENEWING, timeout=2)
        await cli.wait_for_state(State.BOUND, timeout=1)

    assert len(mock_dhcp_server.decoded_requests) == 4
    discover, request, renew_request, release = (
        mock_dhcp_server.decoded_requests
    )

    # First, the client sends a discover:
    assert discover.message_type == dhcp.MessageType.DISCOVER
    # This is a broadcast message
    assert discover.eth_dst == 'ff:ff:ff:ff:ff:ff'
    assert discover.ip_dst == '255.255.255.255'
    assert discover.ip_src == '0.0.0.0'

    assert discover.dhcp['op'] == bootp.MessageType.BOOTREQUEST
    assert discover.dhcp['flags'] == bootp.Flag.BROADCAST
    # all bootp ip addr fields are left blank
    assert all([discover.dhcp[f'{x}iaddr'] == '0.0.0.0' for x in 'cysg'])
    # the requested parameters match those in the client config
    assert discover.dhcp['options']['parameter_list'] == list(
        cfg.requested_parameters
    )
    assert discover.sport, release.dport == (68, 67)

    # The pcap contains an offer in response to the discover.
    # The client sends a request for that offer:
    assert request.message_type == dhcp.MessageType.REQUEST
    # This is a broadcast message
    assert request.eth_dst == 'ff:ff:ff:ff:ff:ff'
    assert request.ip_dst == '255.255.255.255'
    assert request.ip_src == '0.0.0.0'
    assert request.dhcp['op'] == bootp.MessageType.BOOTREQUEST
    assert request.dhcp['flags'] == bootp.Flag.BROADCAST
    assert request.dhcp['options'] == {
        'client_id': {'key': request.eth_src, 'type': 1},
        'message_type': dhcp.MessageType.REQUEST,
        'parameter_list': list(cfg.requested_parameters),
        'requested_ip': '192.168.186.73',
        'server_id': '192.168.186.1',
        'vendor_id': b'pyroute2',
    }
    assert request.sport, release.dport == (68, 67)

    # the server sends an ACK and the client is bound.

    # a while later (actually 1 sec.), the client sends
    # a new REQUEST to renew its lease and switches to RENEWING
    assert renew_request.message_type == dhcp.MessageType.REQUEST
    # it's an unicast request
    assert renew_request.dhcp['flags'] == bootp.Flag.UNICAST
    assert renew_request.eth_dst == '2e:7e:7d:8e:5f:5f'
    assert renew_request.ip_dst == '192.168.186.1'
    assert renew_request.ip_src == '192.168.186.73'
    # no server id nor requested ip in this case
    assert renew_request.dhcp['options'] == {
        'client_id': {'key': renew_request.eth_src, 'type': 1},
        'message_type': dhcp.MessageType.REQUEST,
        'parameter_list': list(cfg.requested_parameters),
        'vendor_id': b'pyroute2',
    }
    assert renew_request.sport, release.dport == (68, 67)

    # since we stopped the client, it sends a RELEASE (unicast too)
    assert release.message_type == dhcp.MessageType.RELEASE
    assert release.dhcp['flags'] == bootp.Flag.UNICAST
    assert release.eth_dst == '2e:7e:7d:8e:5f:5f'
    assert renew_request.ip_dst == '192.168.186.1'
    assert renew_request.ip_src == '192.168.186.73'
    assert release.dhcp['options'] == {
        'client_id': {'key': release.eth_src, 'type': 1},
        'message_type': dhcp.MessageType.RELEASE,
        'server_id': '192.168.186.1',
        'vendor_id': b'pyroute2',
    }
    assert release.sport, release.dport == (68, 67)
