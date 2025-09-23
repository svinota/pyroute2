import asyncio
import json
from operator import itemgetter

import pytest
from fixtures.dhcp_servers.dnsmasq import DnsmasqConfig, DnsmasqFixture
from fixtures.dhcp_servers.udhcpd import UdhcpdFixture
from fixtures.interfaces import DHCPRangeConfig, VethPair
from pr2test.marks import require_root
from test_dhcp.conftest import parse_stdout_leases

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


@pytest.mark.parametrize(
    ('run_dhcp_server_outside_vlan',), ((True,), (False,))
)
async def test_detect_with_vlan(
    udhcpd: UdhcpdFixture,
    veth_pair: VethPair,
    async_ipr: AsyncIPRoute,
    caplog: pytest.LogCaptureFixture,
    run_dhcp_server_outside_vlan: bool,
    async_context,
):
    '''Get an offer from dnsmasq over a vlan,
    and maybe another offer from udhcpd outside of it.

    The vlan on which dnsmasq listens is over the veth pair.
    The socket listening outside of the vlan should *not* receive
    the response sent by dnsmasq.
    '''

    if run_dhcp_server_outside_vlan is False:
        # stop udhcpd, which runs on the veth directly
        await udhcpd.__aexit__(None, None, None)
        # now only dnsmasq will remain, listening on the vlan

    # configure a dhcp range for the vlan
    dnsmasq_range = DHCPRangeConfig(
        start='192.168.11.10',
        end='192.168.11.20',
        router='192.168.11.1',
        broadcast='192.168.11.255',
        netmask='255.255.255.0',
    )
    # create a pair of vlan interfaces over the veth pair
    vlan_id = 151
    srv_vlan_name = f'srv.{vlan_id}'
    cli_vlan_name = f'cli.{vlan_id}'
    await async_ipr.link(
        'add',
        ifname=srv_vlan_name,
        kind='vlan',
        link=veth_pair.server_idx,
        vlan_id=vlan_id,
    )
    await async_ipr.link(
        'add',
        ifname=cli_vlan_name,
        kind='vlan',
        link=veth_pair.client_idx,
        vlan_id=vlan_id,
    )
    srv_vlan_idx = (await async_ipr.link_lookup(ifname=srv_vlan_name))[0]
    cli_vlan_idx = (await async_ipr.link_lookup(ifname=cli_vlan_name))[0]

    # add an ip address only on the server end
    await async_ipr.addr(
        'add',
        index=srv_vlan_idx,
        address=str(dnsmasq_range.router),
        prefixlen=24,
    )

    # bring up both interfaces
    await async_ipr.link('set', index=srv_vlan_idx, state='up')
    await async_ipr.link('set', index=cli_vlan_idx, state='up')

    # run dnsmasq over the vlan
    dnsmasq_cfg = DnsmasqConfig(range=dnsmasq_range, interface=srv_vlan_name)
    async with DnsmasqFixture(dnsmasq_cfg):
        # start the server detector
        process = await asyncio.create_subprocess_exec(
            'dhcp-server-detector',
            veth_pair.client,
            cli_vlan_name,
            # this should send 1 discover and stop
            '--duration=0.9',
            '--interval=1.0',
            '--log-level=DEBUG',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=3
        )
    # we got at least one offer, so the detector returns 0
    assert process.returncode == 0
    # the vlan interface starts with "c" so it's first when sorted this way
    offers = sorted(parse_stdout_leases(stdout), key=itemgetter('interface'))

    assert offers
    # we always get an offer from dnsmasq on the vlan
    vlan_offer = offers[0]
    assert vlan_offer['interface'] == cli_vlan_name
    assert vlan_offer['message']['dhcp']['options']['server_id'] == str(
        dnsmasq_range.router
    )

    if run_dhcp_server_outside_vlan:
        # 2 servers, 2 leases
        assert len(offers) == 2
        # check the offer sent by udhcpd
        non_vlan_offer = offers[1]
        assert non_vlan_offer['interface'] == veth_pair.client
        assert non_vlan_offer['message']['dhcp']['options'][
            'server_id'
        ] == str(udhcpd.config.range.router)
        assert (
            vlan_offer['message']['dhcp']['xid']
            != non_vlan_offer['message']['dhcp']['xid']
        )
    else:
        # we stopped udhcpd so only got an offer from dnsmasq
        assert len(offers) == 1

    # The bpf filter drops packets that are intended for vlans; failing that,
    # we would receive a copy of all packets meant for "upper" vlans when
    # on a non-vlan interface.
    # since we have a different xid per  interface, they're discarded,
    # but should not happen anyway.
    # So if this assert fails it means the BPF filter does not work
    assert b'Got OFFER with xid mismatch, ignoring' not in stderr
