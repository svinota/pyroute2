import asyncio
import json

import pytest
from fixtures.dhcp_servers.dnsmasq import DnsmasqFixture
from fixtures.dhcp_servers.udhcpd import UdhcpdFixture
from fixtures.interfaces import VethPair
from pr2test.marks import require_root

from pyroute2.dhcp.enums import dhcp
from pyroute2.iproute.linux import AsyncIPRoute

pytestmark = [pytest.mark.asyncio, require_root()]


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
    assert process.returncode == 0

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
    assert process.returncode == 0

    # dont bother decoding the json here, we just check we have 2 messages
    assert stdout.decode().count(f'"interface": "{veth_pair.client}"') == 2

    # check we have the expected logs
    logs = [i.decode() for i in stderr.splitlines()]
    assert len(logs) == 4
    assert '-> DISCOVER' in logs[0]
    assert '<- OFFER' in logs[1]
    assert '-> DISCOVER' in logs[2]
    assert '<- OFFER' in logs[3]


async def test_detect_no_response(veth_pair: VethPair):
    '''The detector exits on error when there is no response.'''
    process = await asyncio.create_subprocess_exec(
        'dhcp-server-detector',
        veth_pair.client,
        '--duration=1',
        '--interval=0.9',
        '--log-level=INFO',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
    assert process.returncode == 1  # no response, exited on error
    assert not stdout  # no lease was written
    assert stderr.count(b"DISCOVER") == 2  # 2 requests sent


async def test_detect_wrong_interface():
    '''The only passed interface does not exist.'''
    process = await asyncio.create_subprocess_exec(
        'dhcp-server-detector',
        'definitely_does_not_exist',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
    assert process.returncode == 1
    assert not stdout
    assert (
        "'definitely_does_not_exist': [Errno 2] Link not found"
    ) in stderr.decode()


async def test_interface_goes_down_during_detection(
    udhcpd: UdhcpdFixture, veth_pair: VethPair
):
    '''The interface goes down after a response has been received.'''
    process = await asyncio.create_subprocess_exec(
        'dhcp-server-detector',
        veth_pair.client,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # TODO put in a fixture
    async def shutdown_iface(ifindex: int):
        '''Shuts down the interface after udhcpd sent an offer.'''
        await asyncio.wait_for(udhcpd.wait_for_log('OFFER'), timeout=2)
        async with AsyncIPRoute() as ipr:
            await ipr.link("set", index=ifindex, state='down')

    shutdown_task = asyncio.create_task(
        shutdown_iface(ifindex=veth_pair.client_idx)
    )

    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=3)
    await shutdown_task
    # we still got a response, so exit is successful
    assert process.returncode == 0
    offer = json.loads(stdout)
    assert offer['interface'] == veth_pair.client
    msg = offer['message']
    assert msg['dhcp']['options']['message_type'] == dhcp.MessageType.OFFER
    # there is 1 error log
    assert stderr.count(b'ERROR') == 1
    assert (
        f'{veth_pair.client!r}: [Errno 100] Network is down'
    ) in stderr.decode()
