import asyncio
import json
from ipaddress import IPv4Address
from pathlib import Path

import pytest
from fixtures.dnsmasq import DnsmasqFixture
from fixtures.interfaces import VethPair
from pr2test.marks import require_root

from pyroute2.dhcp import client, fsm
from pyroute2.dhcp.constants import bootp, dhcp
from pyroute2.dhcp.leases import JSONFileLease

pytestmark = [require_root()]


@pytest.mark.asyncio
async def test_get_lease(
    dnsmasq: DnsmasqFixture,
    veth_pair: VethPair,
    tmpdir: str,
    monkeypatch: pytest.MonkeyPatch,
):
    '''The client can get a lease and write it to a file.'''
    work_dir = Path(tmpdir)
    # Patch JSONFileLease so leases get written to the temp dir
    # instead of whatever the working directory is
    monkeypatch.setattr(JSONFileLease, '_get_lease_dir', lambda: work_dir)

    # boot up the dhcp client and wait for a lease
    async with client.AsyncDHCPClient(veth_pair.client) as cli:
        await cli.bootstrap()
        try:
            await asyncio.wait_for(cli.bound.wait(), timeout=5)
        except TimeoutError:
            raise AssertionError(
                f'Timed out. dnsmasq output: {dnsmasq.stderr}'
            )
        assert cli.state == fsm.State.BOUND
        lease = cli.lease
        assert lease.ack['xid'] == cli.xid

    # check the obtained lease
    assert lease.interface == veth_pair.client
    assert lease.ack['op'] == bootp.MessageType.BOOTREPLY
    assert lease.ack['options']['message_type'] == dhcp.MessageType.ACK
    assert (
        dnsmasq.options.range_start
        <= IPv4Address(lease.ip)
        <= dnsmasq.options.range_end
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
async def test_client_console(dnsmasq: DnsmasqFixture, veth_pair: VethPair):
    '''The commandline client can get a lease, print it to stdout and exit.'''
    process = await asyncio.create_subprocess_exec(
        'pyroute2-dhcp-client',
        veth_pair.client,
        '--lease-type',
        'pyroute2.dhcp.leases.JSONStdoutLease',
        '--exit-on-lease',
        stdout=asyncio.subprocess.PIPE,
        # stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=5)
    except TimeoutError:
        raise AssertionError(f'Timed out. dnsmasq output: {dnsmasq.stderr}')
    assert process.returncode == 0
    assert stdout
    json_lease = json.loads(stdout)
    assert json_lease['interface'] == veth_pair.client
    assert (
        dnsmasq.options.range_start
        <= IPv4Address(json_lease['ack']['yiaddr'])
        <= dnsmasq.options.range_end
    )
