import asyncio
import signal
from ipaddress import IPv4Address

import pytest
from fixtures.dhcp_servers.dnsmasq import DnsmasqFixture
from fixtures.dhcp_servers.udhcpd import UdhcpdFixture
from fixtures.interfaces import VethPair
from pr2test.marks import require_root
from test_dhcp.conftest import GetIPv4AddrsFor, parse_stdout_leases

from pyroute2.iproute.linux import AsyncIPRoute

pytestmark = [
    pytest.mark.asyncio,
    require_root(),
    pytest.mark.usefixtures('setns_context'),
]


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
    json_leases = parse_stdout_leases(stdout)
    assert len(json_leases) == 1
    json_lease = json_leases[0]
    assert json_lease['interface'] == veth_pair.client
    assert (
        dnsmasq.config.range.start
        <= IPv4Address(json_lease['ack']['yiaddr'])
        <= dnsmasq.config.range.end
    )


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
    leases = parse_stdout_leases(stdout)
    assert len(leases) == 2
    first_json_lease, second_json_lease = leases
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


async def test_exit_timeout(
    udhcpd: UdhcpdFixture,
    veth_pair: VethPair,
    get_ipv4_addrs_for: GetIPv4AddrsFor,
):
    process = await asyncio.create_subprocess_exec(
        'pyroute2-dhcp-client',
        veth_pair.client,
        '--lease-type',
        'pyroute2.dhcp.leases.JSONStdoutLease',
        '--exit-on-timeout=3',
        '--no-release',
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=5)
    except TimeoutError:
        raise AssertionError(f'Timed out. udhcpd output: {udhcpd.stderr}')
    assert process.returncode == 0
    # check the lease
    assert stdout
    json_leases = parse_stdout_leases(stdout)
    assert len(json_leases) == 1
    json_lease = json_leases[0]
    assert json_lease['interface'] == veth_pair.client
    ip = json_lease['ack']['yiaddr']
    assert udhcpd.stderr[-2:] == [
        f'udhcpd: sending OFFER to {ip}',
        f'udhcpd: sending ACK to {ip}',
    ]

    # since we passed --no-release, the ip is still there on exit
    ips = await get_ipv4_addrs_for(veth_pair.client_idx)
    assert len(ips) == 1
    assert ips[0].get('address') == ip


@pytest.mark.parametrize(
    ('signum', 'expected_signal_log', 'expected_state_change'),
    (
        (
            signal.SIGUSR1,
            'SIGUSR1 received, renewing lease',
            'BOUND -> RENEWING',
        ),
        (
            signal.SIGUSR2,
            'SIGUSR2 received, rebinding lease',
            'BOUND -> REBINDING',
        ),
        (signal.SIGHUP, 'SIGHUP received, resetting', 'BOUND -> INIT'),
    ),
)
async def test_signals(
    dnsmasq: DnsmasqFixture,
    veth_pair: VethPair,
    signum: int,
    expected_signal_log: str,
    expected_state_change: str,
):
    '''Signals can be sent to the client to rene/rebind/reset its lease'''
    # Run a dhcp client
    process = await asyncio.create_subprocess_exec(
        'pyroute2-dhcp-client',
        veth_pair.client,
        '--lease-type',
        'pyroute2.dhcp.leases.JSONStdoutLease',
        '--log-level=DEBUG',
        '--hook',
        'pyroute2.dhcp.hooks.configure_ip',
        '--hook',
        'pyroute2.dhcp.hooks.remove_ip',
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    # wait till the client is bound
    await asyncio.wait_for(dnsmasq.wait_for_log('DHCPACK'), timeout=3)
    dnsmasq.expected_logs.clear()
    await asyncio.sleep(0.2)
    # send a signal to trigger a renewal
    process.send_signal(signum)
    # wait till the client is bound again
    await asyncio.wait_for(dnsmasq.wait_for_log('DHCPACK'), timeout=2)
    await asyncio.sleep(0.2)
    # stop the client
    process.send_signal(signal.SIGINT)
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=2)
    # check the client received the signal
    assert expected_signal_log.encode() in stderr
    assert expected_state_change.encode() in stderr

    # check there are two leases
    leases = parse_stdout_leases(stdout)
    assert len(leases) == 2
    first_lease, second_lease = leases
    first_lease['ack']['yiaddr'] == second_lease['ack']['yiaddr']


async def test_interface_does_not_exist():
    '''The client raises a meaninfgul error
    if the interface does not exist.'''

    process = await asyncio.create_subprocess_exec(
        'pyroute2-dhcp-client', 'doesn0texist', stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()
    assert process.returncode and process.returncode > 0
    assert stderr
    assert (
        stderr.splitlines()[-1].decode()
        == 'pyroute2-dhcp-client: error: Interface not found: doesn0texist'
    )
