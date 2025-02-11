import json
import os
from ipaddress import IPv4Address
from pathlib import Path

import pytest
from fixtures.dhcp_servers.dnsmasq import DnsmasqFixture
from fixtures.dhcp_servers.udhcpd import UdhcpdFixture
from fixtures.interfaces import VethPair
from pr2test.marks import require_root

from pyroute2.dhcp import fsm
from pyroute2.dhcp.client import AsyncDHCPClient, ClientConfig
from pyroute2.dhcp.enums import bootp, dhcp
from pyroute2.dhcp.leases import JSONFileLease, JSONStdoutLease

pytestmark = [require_root()]


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_lease_file(client_config: ClientConfig):
    '''The client must write a pidfile when configured to.'''
    client_config.write_pidfile = True
    async with AsyncDHCPClient(client_config):
        assert client_config.pidfile_path.exists()
        assert int(client_config.pidfile_path.read_text()) == os.getpid()
    assert not client_config.pidfile_path.exists()


@pytest.mark.asyncio
async def test_lease_expiration(udhcpd: UdhcpdFixture, client_config: ClientConfig, caplog: pytest.LogCaptureFixture):
    '''The client must go back to INIT when the lease expires.'''
    caplog.set_level('INFO', logger='pyroute2.dhcp')
    async with AsyncDHCPClient(client_config) as cli:
        await cli.bootstrap()
        # wait for the client to get a lease
        await cli.wait_for_state(fsm.State.BOUND, timeout=5.0)
        # stop udhcpd, so nobody is answering anymore
        await udhcpd.__aexit__(None, None, None)
        # renewing timer expires
        await cli.wait_for_state(fsm.State.RENEWING, timeout=5.0)
        # rebinding timer expires
        await cli.wait_for_state(fsm.State.REBINDING, timeout=5.0)
        # lease expire, we look for a new one
        await cli.wait_for_state(fsm.State.INIT, timeout=5.0)
        await cli.wait_for_state(fsm.State.SELECTING, timeout=5.0)

    assert (
        caplog.messages.index('Renewal timer expired')
        < caplog.messages.index('Rebinding timer expired')
        < caplog.messages.index('Lease expired')
    )
