import json
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
    tmpdir: str,
    monkeypatch: pytest.MonkeyPatch,
):
    '''The client can get a lease from dnsmasq and write it to a file.'''
    work_dir = Path(tmpdir)
    # Patch JSONFileLease so leases get written to the temp dir
    # instead of whatever the working directory is
    monkeypatch.setattr(JSONFileLease, '_get_lease_dir', lambda: work_dir)
    # boot up the dhcp client and wait for a lease
    cfg = ClientConfig(interface=veth_pair.client)
    async with AsyncDHCPClient(cfg) as cli:
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
    '''Test getting a lease, expiring & getting a lease again.'''
    cfg = ClientConfig(interface=veth_pair.client, lease_type=JSONStdoutLease)
    async with AsyncDHCPClient(cfg) as cli:
        # No lease, we're in the INIT state
        assert cli.state == fsm.State.INIT
        # Start requesting an IP
        await cli.bootstrap()
        # Then, the client in the SELECTING state while sending DISCOVERs
        await cli.wait_for_state(fsm.State.SELECTING, timeout=1)
        # Once we get an OFFER the client switches to REQUESTING
        await cli.wait_for_state(fsm.State.REQUESTING, timeout=1)
        # After getting an ACK, we're BOUND !
        await cli.wait_for_state(fsm.State.BOUND, timeout=1)

        # Ideally, we would test the REBINDING & RENEWING states here,
        # but they depend on timers that udhcpd does not implement.

        # The lease expires, and we're back to INIT
        await cli.wait_for_state(fsm.State.INIT, timeout=5)
        await cli.wait_for_state(fsm.State.SELECTING, timeout=1)
        await cli.wait_for_state(fsm.State.REQUESTING, timeout=1)
        await cli.wait_for_state(fsm.State.BOUND, timeout=1)

        # Stop here, that's enough
        lease = cli.lease
        xid = cli.xid
        assert lease
        assert xid

    # The ACK corresponds to a request that was made in the REQUESTING state
    assert lease.ack['xid'] == xid.for_state(fsm.State.REQUESTING)

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
    assert (
        udhcpd.stderr[-4:]
        == [
            f'udhcpd: sending OFFER to {lease.ip}',
            f'udhcpd: sending ACK to {lease.ip}',
        ]
        * 2
    )
