import asyncio
import json

import pytest
from fixtures.dhcp_servers.dnsmasq import DnsmasqFixture
from fixtures.dhcp_servers.udhcpd import UdhcpdFixture
from fixtures.interfaces import VethPair
from pr2test.marks import require_root

from pyroute2.dhcp.enums import dhcp

pytestmark = [require_root()]


@pytest.mark.asyncio
async def test_detect_dnsmasq_once(
    dnsmasq: DnsmasqFixture, veth_pair: VethPair
):
    process = await asyncio.create_subprocess_exec(
        'dhcp-server-detector',
        veth_pair.client,
        '--exit-on-first-offer',
        '--log-level=INFO',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)

    # check the offer was properly encoded
    offer = json.loads(stdout)
    assert offer['interface'] == veth_pair.client
    msg = offer['message']
    assert msg['dhcp']['options']['message_type'] == dhcp.MessageType.OFFER
    assert msg['dhcp']['options']['server_id'] == str(
        dnsmasq.config.range.router
    )
    assert msg['dport'] == 68
    assert msg['sport'] == 67
    assert msg['ip_dst'] == '255.255.255.255'
    assert msg['eth_dst'] == 'ff:ff:ff:ff:ff:ff'

    # check we have the expected logs
    logs = [i.decode() for i in stderr.splitlines()]
    assert len(logs) == 2
    assert f'[{veth_pair.client}] -> DISCOVER' in logs[0]
    assert f'[{veth_pair.client}] <- OFFER from ' in logs[1]


@pytest.mark.asyncio
async def test_detect_udhcpd_multiple(
    udhcpd: UdhcpdFixture, veth_pair: VethPair
):
    process = await asyncio.create_subprocess_exec(
        'dhcp-server-detector',
        veth_pair.client,
        # this should send 2 messages and stop
        '--duration=0.9',
        '--interval=0.5',
        '--log-level=INFO',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
    # dont bother decoding the json here, we just check we have 2 messages
    assert stdout.decode().count(f'"interface": "{veth_pair.client}"') == 2

    # check we have the expected logs
    logs = [i.decode() for i in stderr.splitlines()]
    assert len(logs) == 4
    assert '-> DISCOVER' in logs[0]
    assert '<- OFFER' in logs[1]
    assert '-> DISCOVER' in logs[2]
    assert '<- OFFER' in logs[3]
