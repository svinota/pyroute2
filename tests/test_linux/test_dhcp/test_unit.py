import asyncio
from typing import Callable

import pytest
from fixtures.dhcp_servers.mock import MockDHCPServerFixture
from fixtures.interfaces import VethPair

from pyroute2.dhcp.client import (
    AsyncDHCPClient,
    ClientConfig,
    randomized_increasing_backoff,
)
from pyroute2.dhcp.dhcp4msg import dhcp4msg
from pyroute2.dhcp.enums import bootp, dhcp
from pyroute2.dhcp.fsm import State
from pyroute2.dhcp.leases import JSONFileLease

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    ('dhcp_client_host_name',), (('nebuchadnezzar',), (None,))
)
@pytest.mark.parametrize(
    ('dhcp_client_vendor_id',), (('fake-vendor-id',), (None,))
)
async def test_get_and_renew_lease(
    mock_dhcp_server: MockDHCPServerFixture,
    set_fixed_xid: Callable[[int], None],
    client_config: ClientConfig,
    caplog: pytest.LogCaptureFixture,
):
    '''A lease is obtained with a 1s renewing time, the client renews it.

    The test pcap file contains the OFFER & the 2 ACKs.
    '''
    caplog.set_level('INFO')

    expected_vid_and_hostname = {}
    if vid := client_config.vendor_id:
        # vendor id must be present only if configured
        expected_vid_and_hostname['vendor_id'] = vid
    if hn := client_config.host_name:
        # same for host_name
        expected_vid_and_hostname['host_name'] = hn

    # Make xids non random so they match the ones in the pcap
    set_fixed_xid(0x12345670)
    async with AsyncDHCPClient(client_config) as cli:
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
        client_config.requested_parameters
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
        'parameter_list': list(client_config.requested_parameters),
        'requested_ip': '192.168.186.73',
        'server_id': '192.168.186.1',
        **expected_vid_and_hostname,
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
        'parameter_list': list(client_config.requested_parameters),
        **expected_vid_and_hostname,
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
        **expected_vid_and_hostname,
    }
    assert release.sport, release.dport == (68, 67)


async def test_ack_invalid_request_state(
    mock_dhcp_server: MockDHCPServerFixture,
    set_fixed_xid: Callable[[int], None],
    client_config: ClientConfig,
    caplog: pytest.LogCaptureFixture,
):
    '''An ack received with an invalid request state in its xid
    must cause a warning to be logged and the lease to be ignored.
    '''
    caplog.set_level('WARNING')
    # Make xids non random so they match the ones in the pcap
    set_fixed_xid(0x12345670)
    async with AsyncDHCPClient(client_config) as cli:
        await cli.bootstrap()
        await cli.wait_for_state(State.SELECTING, timeout=1)
        # server sends an OFFER
        await cli.wait_for_state(State.REQUESTING, timeout=1)
        # server sends an ACK, which is ignored by the client
        await asyncio.sleep(0.2)
        assert cli.lease is None

    assert caplog.messages == ['Invalid request state for xid 0x1234567f']
    assert len(mock_dhcp_server.decoded_requests) == 2
    discover, request = mock_dhcp_server.decoded_requests
    assert discover.message_type == dhcp.MessageType.DISCOVER
    assert request.message_type == dhcp.MessageType.REQUEST


async def test_init_reboot_nak(
    mock_dhcp_server: MockDHCPServerFixture,
    client_config: ClientConfig,
    veth_pair: VethPair,
    caplog: pytest.LogCaptureFixture,
    set_fixed_xid: Callable[[int], None],
):
    '''The server doesn't like the requested IP in INIT-REBOOT.

    It sends a NAK and the client goes back to INIT and gets a new lease.
    '''
    set_fixed_xid(0xDD435A20)
    caplog.set_level('INFO')
    # Create a fake lease to start the client in INIT-REBOOT
    old_lease = JSONFileLease(
        ack=dhcp4msg(
            {
                'op': bootp.MessageType.BOOTREPLY,
                'flags': bootp.Flag.BROADCAST,
                'yiaddr': '192.168.186.73',
                'chaddr': '72:c1:55:6f:76:83',
                'options': {
                    'message_type': 5,
                    'server_id': '192.168.186.1',
                    'lease_time': 1,
                },
            }
        ),
        interface=veth_pair.client,
        server_mac='2e:7e:7d:8e:5f:5f',
    )
    old_lease.dump()
    async with AsyncDHCPClient(client_config) as cli:
        await cli.bootstrap()
        # The client loaded the lease we just wrote and sents a REQUEST
        await cli.wait_for_state(State.REBOOTING, timeout=1)
        # The server sends a NAK, so the client goes back to INIT
        await cli.wait_for_state(State.INIT, timeout=1)
        await cli.wait_for_state(State.SELECTING, timeout=1)
        # The server sends an OFFER an the client requests it
        await cli.wait_for_state(State.REQUESTING, timeout=1)
        # The servers ACKs the request and we're bound !
        await cli.wait_for_state(State.BOUND, timeout=1)

    assert len(mock_dhcp_server.decoded_requests) == 4
    request1, discover, request2, release = mock_dhcp_server.decoded_requests
    assert request1.message_type == dhcp.MessageType.REQUEST
    assert request1.dhcp['flags'] == bootp.Flag.BROADCAST
    assert request1.dhcp['op'] == bootp.MessageType.BOOTREQUEST
    assert request1.dhcp['options']['requested_ip'] == old_lease.ip
    assert request1.eth_dst == 'ff:ff:ff:ff:ff:ff'
    assert request1.ip_dst == '255.255.255.255'
    assert request1.ip_src == '0.0.0.0'

    assert discover.message_type == dhcp.MessageType.DISCOVER
    assert discover.dhcp['flags'] == bootp.Flag.BROADCAST
    assert discover.dhcp['op'] == bootp.MessageType.BOOTREQUEST
    assert discover.eth_dst == 'ff:ff:ff:ff:ff:ff'
    assert discover.ip_dst == '255.255.255.255'
    assert discover.ip_src == '0.0.0.0'

    assert request2.message_type == dhcp.MessageType.REQUEST
    assert request2.dhcp['flags'] == bootp.Flag.BROADCAST
    assert request2.dhcp['op'] == bootp.MessageType.BOOTREQUEST
    assert request2.eth_dst == 'ff:ff:ff:ff:ff:ff'
    assert request2.ip_dst == '255.255.255.255'
    assert request2.ip_src == '0.0.0.0'

    assert release.message_type == dhcp.MessageType.RELEASE
    assert release.dhcp['flags'] == bootp.Flag.UNICAST
    assert release.dhcp['op'] == bootp.MessageType.BOOTREQUEST
    assert release.eth_dst == '2e:7e:7d:8e:5f:5f'
    assert release.ip_dst == '192.168.186.1'
    assert release.ip_src == '192.168.186.85'


async def test_requesting_timeout(
    mock_dhcp_server: MockDHCPServerFixture,
    client_config: ClientConfig,
    caplog: pytest.LogCaptureFixture,
    set_fixed_xid: Callable[[int], None],
):
    '''The client resets itself after a timeout in the REQUESTING state.'''
    set_fixed_xid(0xDD435A20)
    caplog.set_level('INFO')
    # Timeout after 1s when requesting an offer and no answer
    client_config.timeouts[State.REQUESTING] = 1
    async with AsyncDHCPClient(client_config) as cli:
        await cli.bootstrap()
        # The client sends a DISCOVER, the servers sends an OFFER
        await cli.wait_for_state(State.SELECTING, timeout=1)
        await cli.wait_for_state(State.REQUESTING, timeout=1)
        # and then the server nevers send an ack
        # the client goes back to SELECTING after the timeout
        await cli.wait_for_state(State.SELECTING, timeout=3)

    # the client has reset
    assert 'Resetting after 1.0 seconds' in caplog.messages

    assert len(mock_dhcp_server.decoded_requests) == 2
    discover, request = mock_dhcp_server.decoded_requests

    assert discover.message_type == dhcp.MessageType.DISCOVER
    assert discover.dhcp['flags'] == bootp.Flag.BROADCAST
    assert discover.dhcp['op'] == bootp.MessageType.BOOTREQUEST
    assert discover.eth_dst == 'ff:ff:ff:ff:ff:ff'
    assert discover.ip_dst == '255.255.255.255'
    assert discover.ip_src == '0.0.0.0'
    assert discover.dhcp['options']['parameter_list'] == list(
        client_config.requested_parameters
    )

    assert request.message_type == dhcp.MessageType.REQUEST
    assert request.dhcp['flags'] == bootp.Flag.BROADCAST
    assert request.dhcp['op'] == bootp.MessageType.BOOTREQUEST
    assert request.eth_dst == 'ff:ff:ff:ff:ff:ff'
    assert request.ip_dst == '255.255.255.255'
    assert request.ip_src == '0.0.0.0'
    assert request.dhcp['options']['parameter_list'] == list(
        client_config.requested_parameters
    )


async def test_wait_for_state_timeout(client_config: ClientConfig):
    '''wait_for_state() can timeout after a given delay'''
    async with AsyncDHCPClient(client_config) as cli:
        with pytest.raises(asyncio.exceptions.TimeoutError) as err_ctx:
            await cli.wait_for_state(State.BOUND, timeout=0.2)
    assert (
        str(err_ctx.value)
        == 'Timed out waiting for the BOUND state. Current state: INIT'
    )


async def test_offer_wrong_xid(
    client_config: ClientConfig,
    mock_dhcp_server: MockDHCPServerFixture,
    set_fixed_xid: Callable[[int], None],
    caplog: pytest.LogCaptureFixture,
):
    '''The client discards & logs packets with an unknown xid.

    Since we just need a dhcp offer, the pcap for this test
    is a symlink to the one for test_requesting_timeout
    '''
    set_fixed_xid(0x98765432)
    caplog.set_level('ERROR')
    async with AsyncDHCPClient(client_config) as cli:
        await cli.bootstrap()
        await cli.wait_for_state(State.SELECTING, timeout=1)
        # wait a tiny bit for the offer to arrive
        await asyncio.sleep(0.5)
    assert caplog.messages == [
        'Incorrect xid 0xdd435a25 (expected 0x9876543X), discarding'
    ]

    assert len(mock_dhcp_server.decoded_requests) == 1
    discover = mock_dhcp_server.decoded_requests[0]
    assert discover.message_type == dhcp.MessageType.DISCOVER


async def test_unknown_message(
    client_config: ClientConfig,
    mock_dhcp_server: MockDHCPServerFixture,
    caplog: pytest.LogCaptureFixture,
    set_fixed_xid: Callable[[int], None],
):
    '''Unknown messages must be discarded.'''
    set_fixed_xid(0x8F506FD0)
    caplog.set_level('DEBUG', logger='pyroute2.dhcp.client')
    async with AsyncDHCPClient(client_config) as cli:
        await cli.bootstrap()
        # wait a tiny bit for the packet to arrive
        await asyncio.sleep(0.5)
    # the capture contains a request, which the client does not handle
    assert 'DHCP REQUEST messages are not handled'
    assert len(mock_dhcp_server.decoded_requests) == 1


async def test_wrong_state_change(client_config: ClientConfig):
    '''One cannot trigger a state change like that.'''
    async with AsyncDHCPClient(client_config) as cli:
        with pytest.raises(ValueError) as err_ctx:
            await cli.transition(State.BOUND)
    assert str(err_ctx.value) == 'Cannot transition from INIT to BOUND'


async def test_unexpected_dhcp_message(
    client_config: ClientConfig,
    mock_dhcp_server: MockDHCPServerFixture,
    set_fixed_xid: Callable[[int], None],
    caplog: pytest.LogCaptureFixture,
):
    '''Client sends a DISCOVER, the server sends an ACK, it is ignored.'''
    caplog.set_level('DEBUG', logger='pyroute2.dhcp')
    set_fixed_xid(0x12345670)
    async with AsyncDHCPClient(client_config) as cli:
        await cli.bootstrap()
        await cli.wait_for_state(State.SELECTING, timeout=1)
        # TODO: if we want to avoid a sleep here, we should include an
        # OFFER and another ACK in the pcap, so we can simply wait for
        # the client to be bound.
        await asyncio.sleep(0.2)
        # The client is still SELECTING: it didn't receive an OFFER
        assert cli.state == State.SELECTING
    assert (
        'Ignoring call to \'ack_received\' in SELECTING state'
        in caplog.messages
    )
    assert len(mock_dhcp_server.decoded_requests) == 1
    discover = mock_dhcp_server.decoded_requests[0]
    assert discover.message_type == dhcp.MessageType.DISCOVER


async def test_backoff():
    '''Test that the function generating wait times works as expected.'''
    backoff = randomized_increasing_backoff()
    wait_times = [next(backoff) for _ in range(100)]
    assert min(wait_times) == 4.0
    assert max(wait_times) == 32.0
    assert len([i for i in wait_times if 4.0 < i < 32.0]) > 2
    assert sorted(wait_times) == wait_times


@pytest.mark.parametrize(
    'bad_lease_data',
    (
        'not json',
        '{"unexpected": "json"}',
        '"valid json (?) but still unexpected"',
    ),
)
async def test_corrupted_lease_file(
    client_config: ClientConfig,
    caplog: pytest.LogCaptureFixture,
    bad_lease_data: str,
):
    caplog.set_level('WARNING', logger='pyroute2.dhcp.client')
    JSONFileLease._get_path(client_config.interface).write_text(bad_lease_data)
    async with AsyncDHCPClient(client_config) as cli:
        assert cli.lease is None
    assert len(caplog.messages) == 1
    assert caplog.messages[0].startswith('Error loading lease: ')


@pytest.mark.parametrize(
    ('truncate_offset', 'err_prefix'),
    (
        (30, 'Cannot decode ip4msg dst'),
        (150, 'Cannot decode dhcp4msg file'),
        (300, 'Cannot decode option 58 as >i'),
        (330, 'Cannot decode option 6 as string'),
    ),
)
async def test_truncated_packet(
    client_config: ClientConfig,
    caplog: pytest.LogCaptureFixture,
    mock_dhcp_server: MockDHCPServerFixture,
    set_fixed_xid: Callable[[int], None],
    truncate_offset: int,
    err_prefix: str,
):
    '''Test the client does not crash on invalid/truncated packets.'''
    mock_dhcp_server.truncate_at = truncate_offset
    caplog.set_level('ERROR', logger='pyroute2.dhcp.client')
    set_fixed_xid(0x8057FB00)
    async with AsyncDHCPClient(client_config) as cli:
        await cli.bootstrap()
        await asyncio.sleep(0.2)
        # check nothing crashed
        assert cli.state == State.SELECTING
        assert not cli._receiver_task.done()
        assert not cli._sender_task.done()
    assert len(caplog.messages) == 1
    assert caplog.messages[0].startswith(err_prefix)
