import asyncio
import json
import signal
from ipaddress import IPv4Address

import pytest
from fixtures.dhcp_servers.dnsmasq import DnsmasqFixture
from fixtures.interfaces import VethPair
from pr2test.marks import require_root

from pyroute2.iproute.linux import AsyncIPRoute

pytestmark = [require_root(), pytest.mark.usefixtures('setns_context')]


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


@pytest.mark.asyncio
async def test_interface_flaps(dnsmasq: DnsmasqFixture, veth_pair: VethPair):
    # Run a dhcp client
    process = await asyncio.create_subprocess_exec(
        'pyroute2-dhcp-client',
        veth_pair.client,
        '--lease-type',
        'pyroute2.dhcp.leases.JSONStdoutLease',
        '--log-level=INFO',
        '--hook',
        'pyroute2.dhcp.hooks.configure_ip',
        '--hook',
        'pyroute2.dhcp.hooks.remove_ip',
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    # TODO: check the interface has an IP
    res_tsk = asyncio.Task(process.communicate())
    await asyncio.sleep(3)
    # put iface down
    async with AsyncIPRoute() as ipr:
        await ipr.link('set', index=veth_pair.client_idx, state='down')
    await asyncio.sleep(0.5)
    # TODO: check the interface has no IP anymore
    # up again
    async with AsyncIPRoute() as ipr:
        await ipr.link('set', index=veth_pair.client_idx, state='up')

    # stop client
    await asyncio.sleep(2)
    # TODO: check the interface has an IP again
    process.send_signal(signal.SIGINT)
    stdout, stderr = await asyncio.wait_for(res_tsk, timeout=5)
    assert process.returncode == 0
    # TODO: check the interface has no IP anymore

    # check the logs mention the interface flapping
    logs = stderr.decode()
    assert logs, 'not a single lease'
    assert logs.index(f'{veth_pair.client} went down') < logs.index(
        f'Waiting for {veth_pair.client} to go up...'
    )

    # check we got 2 leases
    middle_of_jsons = stdout.index(b'\n{\n') + 1
    first_json_lease = json.loads(stdout[:middle_of_jsons])
    second_json_lease = json.loads(stdout[middle_of_jsons:])
    assert (
        first_json_lease['ack']['options']
        == second_json_lease['ack']['options']
    )


@pytest.mark.parametrize(
    ('switch', 'value', 'err_msg'),
    (
        (
            '--lease-type',
            'meublé',
            '\'meublé\' must point to a Lease subclass.',
        ),
        (
            '--hook',
            'captain.hook',
            '\'captain.hook\' must point to a valid hook.',
        ),
    ),
)
@pytest.mark.asyncio
async def test_wrong_custom_hook_or_lease(
    switch: str, value: str, err_msg: str
):
    process = await asyncio.create_subprocess_exec(
        'pyroute2-dhcp-client',
        'irrelevantIface',
        switch,
        value,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    assert process.returncode > 0
    assert stderr
    assert stderr.splitlines()[-1].decode().endswith(err_msg)
