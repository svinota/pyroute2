import json
import os
from ipaddress import IPv4Address
from pathlib import Path

import pytest
from fixtures.dhcp_servers.dnsmasq import DnsmasqFixture
from fixtures.dhcp_servers.udhcpd import UdhcpdFixture
from fixtures.interfaces import VethPair
from pr2test.marks import require_root

from pyroute2.dhcp import fsm, hooks
from pyroute2.dhcp.client import AsyncDHCPClient, ClientConfig
from pyroute2.dhcp.enums import bootp, dhcp
from pyroute2.dhcp.leases import JSONFileLease, JSONStdoutLease
from pyroute2.fixtures.iproute import TestContext
from pyroute2.iproute.linux import AsyncIPRoute

pytestmark = [require_root(), pytest.mark.asyncio]


async def test_get_lease_from_dnsmasq(
    dnsmasq: DnsmasqFixture,
    veth_pair: VethPair,
    client_config: ClientConfig,
    tmpdir: str,
    monkeypatch: pytest.MonkeyPatch,
):
    '''The client can get a lease from dnsmasq and write it to a file.'''
    work_dir = Path(tmpdir)
    # Patch JSONFileLease so leases get written to the temp dir
    # instead of whatever the working directory is
    monkeypatch.setattr(JSONFileLease, '_get_lease_dir', lambda: work_dir)
    # boot up the dhcp client and wait for a lease
    async with AsyncDHCPClient(client_config) as cli:
        await cli.bootstrap()
        await cli.wait_for_state(fsm.State.BOUND, timeout=10)
        assert cli.state == fsm.State.BOUND
        lease = cli.lease
        xid = cli.xid
        assert lease
        assert xid

    assert lease.ack['xid'] == xid.for_state(fsm.State.REQUESTING)

    # check the obtained lease
    assert lease.interface == veth_pair.client
    assert lease.ack['op'] == bootp.MessageType.BOOTREPLY
    assert lease.ack['options']['message_type'] == dhcp.MessageType.ACK
    assert lease.ack['options']['lease_time'] == dnsmasq.config.lease_time
    assert (
        lease.ack['options']['renewal_time'] == dnsmasq.config.lease_time / 2
    )
    assert lease.expiration_in > lease.rebinding_in > lease.renewal_in > 0
    assert lease.expired is False
    assert lease.server_id == str(dnsmasq.config.range.router)
    assert lease.routers == [str(dnsmasq.config.range.router)]
    assert (
        dnsmasq.config.range.start
        <= IPv4Address(lease.ip)
        <= dnsmasq.config.range.end
    )
    assert lease.ack['chaddr']
    # TODO: check chaddr matches veth_pair.client's MAC

    # check the lease was written to disk and can be loaded
    expected_lease_file = JSONFileLease._get_path(lease.interface)
    assert expected_lease_file.is_file()
    json_lease = json.loads(expected_lease_file.read_bytes())
    assert isinstance(json_lease, dict)
    assert JSONFileLease(**json_lease) == lease


@pytest.mark.parametrize('lease_time', [5])
async def test_short_udhcpd_lease(udhcpd: UdhcpdFixture, veth_pair: VethPair):
    '''Test getting a lease from udhcpd and renewing it.'''
    cfg = ClientConfig(interface=veth_pair.client, lease_type=JSONStdoutLease)
    async with AsyncDHCPClient(cfg) as cli:
        # No lease, we're in the INIT state
        assert cli.state == fsm.State.INIT
        # Start requesting an IP
        await cli.bootstrap()
        xid = cli.xid
        # Then, the client in the SELECTING state while sending DISCOVERs
        await cli.wait_for_state(fsm.State.SELECTING, timeout=1)
        # Once we get an OFFER the client switches to REQUESTING
        await cli.wait_for_state(fsm.State.REQUESTING, timeout=1)
        # After getting an ACK, we're BOUND !
        await cli.wait_for_state(fsm.State.BOUND, timeout=1)
        # ACK corresponds to a request that was made in the REQUESTING state
        assert cli.lease.ack['xid'] == xid.for_state(fsm.State.REQUESTING)

        # a few seconds later, the renewal timer expires
        await cli.wait_for_state(fsm.State.RENEWING, timeout=3)
        # and we're bound again
        await cli.wait_for_state(fsm.State.BOUND, timeout=1)
        # ACK corresponds to a request that was made in the RENEWING state
        assert cli.lease.ack['xid'] == xid.for_state(fsm.State.RENEWING)

        # Stop here, that's enough
        lease = cli.lease
        assert lease
        assert xid

    # The obtained IP must be in the range
    assert (
        udhcpd.config.range.start
        <= IPv4Address(lease.ip)
        <= udhcpd.config.range.end
    )
    # check the lease
    assert lease.server_id == str(udhcpd.config.range.router)
    assert lease.routers == [str(udhcpd.config.range.router)]
    assert lease.interface == veth_pair.client
    assert lease.ack["options"]["lease_time"] == udhcpd.config.lease_time
    # Check udhcpd output matches our expectations
    assert udhcpd.stderr[-3:] == [
        f'udhcpd: sending OFFER to {lease.ip}',
        f'udhcpd: sending ACK to {lease.ip}',
        f'udhcpd: sending ACK to {lease.ip}',
    ]


async def test_lease_file(client_config: ClientConfig):
    '''The client must write a pidfile when configured to.'''
    client_config.write_pidfile = True
    async with AsyncDHCPClient(client_config):
        assert client_config.pidfile_path.exists()
        assert int(client_config.pidfile_path.read_text()) == os.getpid()
    assert not client_config.pidfile_path.exists()


@pytest.mark.parametrize('lease_time', [5])
async def test_lease_expiration(
    udhcpd: UdhcpdFixture,
    client_config: ClientConfig,
    caplog: pytest.LogCaptureFixture,
    lease_time: int,
):
    '''The client must go back to INIT when the lease expires.'''
    caplog.set_level('INFO', logger='pyroute2.dhcp')
    async with AsyncDHCPClient(client_config) as cli:
        await cli.bootstrap()
        # wait for the client to get a lease
        await cli.wait_for_state(fsm.State.RENEWING, timeout=5.0)
        # stop udhcpd, so nobody is answering anymore
        await udhcpd.__aexit__(None, None, None)
        # renewing timer expires
        await cli.wait_for_state(fsm.State.RENEWING, timeout=5.0)
        # rebinding timer expires
        await cli.wait_for_state(fsm.State.REBINDING, timeout=5.0)
        # lease expire, we look for a new one
        await cli.wait_for_state(fsm.State.INIT, timeout=5.0)
        await cli.wait_for_state(fsm.State.SELECTING, timeout=5.0)
    # Check the lease scheduling logs are emitted in the right order
    timer_logs_args = [
        i.args for i in caplog.records if i.msg.startswith('Scheduling')
    ]
    assert timer_logs_args[0][0] == 'renewal'
    assert timer_logs_args[1][0] == 'rebinding'
    assert timer_logs_args[2][0] == 'expiration'
    # check the computed rebinding times are consistent
    assert (
        0
        < timer_logs_args[0][1]
        < timer_logs_args[1][1]
        < timer_logs_args[2][1]
        <= lease_time
    )
    assert (
        caplog.messages.index('T1 expired, renewing lease')
        < caplog.messages.index('T2 expired, rebinding lease')
        < caplog.messages.index('Lease expired')
    )


async def test_mac_addr_change_same_client_id(
    dnsmasq: DnsmasqFixture,
    client_config: ClientConfig,
    veth_pair: VethPair,
    caplog: pytest.LogCaptureFixture,
    async_context: TestContext[AsyncIPRoute],
    monkeypatch: pytest.MonkeyPatch,
):
    '''The mac addr can change during the lease lifetime, renewing works'''
    new_mac = '06:06:06:06:06:06'
    caplog.set_level('INFO', logger='pyroute2.ext.rawsocket')
    caplog.set_level('DEBUG', logger='pyroute2.dhcp')
    client_config.client_id = b'Coucou'
    # make sure the ip is configured, which is assumed by the client when bound
    client_config.hooks = [hooks.configure_ip]
    # renew & rebind earlier than dnsmasq tells the client (min. 60s)
    monkeypatch.setattr('pyroute2.dhcp.leases.Lease.renewal_in', 1.0)
    monkeypatch.setattr('pyroute2.dhcp.leases.Lease.rebinding_in', 3.0)
    async with AsyncDHCPClient(client_config) as cli:
        await cli.bootstrap()
        # wait for the client to get a lease
        await cli.wait_for_state(fsm.State.BOUND, timeout=5.0)
        first_lease = cli.lease
        # change the mac addr
        await async_context.ipr.link(
            'set', index=veth_pair.client_idx, address=new_mac
        )
        # wait for the client to renew
        await cli.wait_for_state(fsm.State.RENEWING, timeout=5.0)
        # dnsmasq should have renewed the lease even though the mac changed
        await cli.wait_for_state(fsm.State.BOUND, timeout=5.0)
        second_lease = cli.lease
    # the client's mac addr was indeed changed
    assert cli._sock.l2addr == new_mac
    assert second_lease.ack['chaddr'] == new_mac
    assert first_lease.ack['chaddr'] != new_mac
    assert any(
        (
            f'l2addr for {veth_pair.client} changed' in i
            for i in caplog.messages
        )
    )
    # but not the ip
    assert first_lease.ip == second_lease.ip
    assert first_lease.obtained < second_lease.obtained
    assert first_lease.ack['xid'] != second_lease.ack['xid']


@pytest.mark.parametrize('lease_time', [5])
async def test_mac_addr_change(
    udhcpd: UdhcpdFixture,
    client_config: ClientConfig,
    veth_pair: VethPair,
    caplog: pytest.LogCaptureFixture,
    async_context: TestContext[AsyncIPRoute],
):
    caplog.set_level('INFO', logger='pyroute2.ext.rawsocket')
    caplog.set_level('INFO', logger='pyroute2.dhcp')
    async with AsyncDHCPClient(client_config) as cli:
        '''The mac (& client id) changes, we have to re-discover.'''
        await cli.bootstrap()
        # wait for the client to get a lease
        await cli.wait_for_state(fsm.State.BOUND, timeout=5.0)
        first_ip = cli.lease.ip
        # change the mac addr
        await async_context.ipr.link(
            'set', index=veth_pair.client_idx, address='06:06:06:06:06:06'
        )
        # the client renews after a very short while
        await cli.wait_for_state(fsm.State.RENEWING, timeout=5.0)
        # since the mac (and client id) changed, the server does not answer
        await cli.wait_for_state(fsm.State.REBINDING, timeout=5.0)
        # we go back to discover
        await cli.wait_for_state(fsm.State.SELECTING, timeout=5.0)
        await cli.wait_for_state(fsm.State.REQUESTING, timeout=5.0)
        # dnsmasq should have renewed the lease with a different ip
        await cli.wait_for_state(fsm.State.BOUND, timeout=5.0)
        second_ip = cli.lease.ip
        assert second_ip != first_ip

    # the client's mac addr was indeed changed
    assert any(
        [
            f'l2addr for {veth_pair.client} changed' in i
            for i in caplog.messages
        ]
    )
    assert cli._sock.l2addr == '06:06:06:06:06:06'
    # udhcpd sent 2 offers and 2 acks
    assert udhcpd.stderr[-4:] == [
        f'udhcpd: sending OFFER to {first_ip}',
        f'udhcpd: sending ACK to {first_ip}',
        f'udhcpd: sending OFFER to {second_ip}',
        f'udhcpd: sending ACK to {second_ip}',
    ]


@pytest.mark.parametrize('delete_lease', (True, False))
@pytest.mark.parametrize('release', (True, False))
async def test_fixed_client_id_changing_mac(
    dnsmasq: DnsmasqFixture,
    client_config: ClientConfig,
    veth_pair: VethPair,
    caplog: pytest.LogCaptureFixture,
    async_context: TestContext[AsyncIPRoute],
    release: bool,
    delete_lease: bool,
):
    '''When using a fixed client id, the client keeps its IP,
    even when the mac changes.

    But if the lease is released and deleted locally, the client
    will send a DISCOVER with a different mac & will be granted
    a new IP.
    '''
    caplog.set_level('INFO', logger='pyroute2.ext.rawsocket')
    caplog.set_level('INFO', logger='pyroute2.dhcp')
    client_config.client_id = b'test'
    client_config.release = release

    # get an initial lease
    async with AsyncDHCPClient(client_config) as cli:
        await cli.bootstrap()
        await cli.wait_for_state(fsm.State.BOUND, timeout=3.0)
        first_lease = cli.lease

    # change the mac addr
    await async_context.ipr.link(
        'set', index=veth_pair.client_idx, address='06:06:06:06:06:06'
    )
    if delete_lease:
        JSONFileLease._get_path(veth_pair.client).unlink()

    # get a second lease
    async with AsyncDHCPClient(client_config) as cli:
        await cli.bootstrap()
        await cli.wait_for_state(fsm.State.BOUND, timeout=3.0)
        second_lease = cli.lease

    if release:
        await dnsmasq.wait_for_log('DHCPRELEASE')

    if release and delete_lease:
        # the lease was released from the server and deleted locally,
        # and the mac changed: we might get another IP but withot guarantee
        # assert first_lease.ip != second_lease.ip
        pass
    else:
        # the mac changed, but the client id stays the same so we're
        # supposed to get the same ip twice
        assert first_lease.ip == second_lease.ip
    assert first_lease.ack['chaddr'] != second_lease.ack['chaddr']
    assert second_lease.ack['chaddr'] == '06:06:06:06:06:06'
    assert first_lease.obtained < second_lease.obtained

    # check logs
    logged_releases = [i for i in dnsmasq.stderr if 'DHCPRELEASE' in i]
    if release:
        assert len(logged_releases) == 2
    else:
        assert not logged_releases

    init_count = caplog.messages.count('OFF -> INIT')
    init_reboot_count = caplog.messages.count('OFF -> INIT_REBOOT')
    if delete_lease:
        # since the lease was deleted the client started from scratch twice
        assert init_count == 2
        assert init_reboot_count == 0
    else:
        # the second run read the existing lease
        assert init_reboot_count == 1
        assert init_count == 1


@pytest.mark.parametrize('lease_time', [-1])
async def test_infinite_lease(
    dnsmasq: DnsmasqFixture,
    client_config: ClientConfig,
    caplog: pytest.LogCaptureFixture,
):
    '''Infinite leases are supported.'''
    caplog.set_level('DEBUG', logger='pyroute2.dhcp')
    async with AsyncDHCPClient(config=client_config) as cli:
        await cli.bootstrap()
        await cli.wait_for_state(fsm.State.BOUND, timeout=3.0)
        lease = cli.lease
    assert 'renewal time is infinite' in caplog.messages
    assert lease.lease_time == -1
    assert lease.expiration_in is None
    assert lease.rebinding_in is None
    assert lease.renewal_in is None
    assert lease.expired is False


async def test_lease_write_failure(
    dnsmasq: DnsmasqFixture,
    client_config: ClientConfig,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    '''Failure to write a lease should not crash the client.'''
    caplog.set_level("ERROR")
    # Create a temp workdir for the test and delete it
    # while the client is running
    wd = tmp_path / "will_be_deleted"
    wd.mkdir()
    monkeypatch.chdir(wd)
    async with AsyncDHCPClient(config=client_config) as cli:
        await cli.bootstrap()
        wd.rmdir()
        await cli.wait_for_state(fsm.State.BOUND, timeout=3.0)
    assert caplog.messages == [
        'Could not dump lease: [Errno 2] No such file or directory'
    ]
