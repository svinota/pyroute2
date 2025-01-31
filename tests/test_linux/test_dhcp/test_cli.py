import asyncio
import json
import signal
from ipaddress import IPv4Address

import pytest
from fixtures.dhcp_servers.dnsmasq import DnsmasqFixture
from fixtures.interfaces import VethPair
from pr2test.marks import require_root

pytestmark = [require_root()]


@pytest.mark.asyncio
async def test_client_console(dnsmasq: DnsmasqFixture, veth_pair: VethPair):
    '''The commandline client can get a lease, print it to stdout and exit.'''
    process = await asyncio.create_subprocess_exec(
        'pyroute2-dhcp-client',
        veth_pair.client,
        '--lease-type',
        'pyroute2.dhcp.leases.JSONStdoutLease',
        '--exit-on-timeout=5',
        '--log-level=DEBUG',
        stdout=asyncio.subprocess.PIPE,
    )

    asyncio.get_running_loop().call_later(
        2, process.send_signal, signal.SIGINT
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
        dnsmasq.config.range.start
        <= IPv4Address(json_lease['ack']['yiaddr'])
        <= dnsmasq.config.range.end
    )
