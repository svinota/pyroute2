import random
from ipaddress import IPv4Address
from pathlib import Path
from typing import AsyncGenerator, NamedTuple

import pytest
import pytest_asyncio

from pyroute2.common import uifname
from pyroute2.fixtures.iproute import SetNSContext, TestContext
from pyroute2.iproute.linux import AsyncIPRoute


class DHCPRangeConfig(NamedTuple):
    start: IPv4Address
    end: IPv4Address
    router: IPv4Address
    broadcast: IPv4Address
    netmask: IPv4Address


@pytest.fixture
def dhcp_range() -> DHCPRangeConfig:
    '''An IPv4 DHCP range configuration.'''
    rangeidx = random.randint(1, 254)
    return DHCPRangeConfig(
        start=IPv4Address(f'10.{rangeidx}.0.10'),
        end=IPv4Address(f'10.{rangeidx}.0.20'),
        router=IPv4Address(f'10.{rangeidx}.0.1'),
        broadcast=IPv4Address(f'10.{rangeidx}.0.255'),
        netmask=IPv4Address('255.255.255.0'),
    )


class VethPair(NamedTuple):
    '''A pair of veth interfaces.'''

    server: str
    client: str
    server_idx: int
    client_idx: int


def accept_local(ifname: str):
    '''Turn on the accept_local sysctl for the given interface.

    This seems to be required for arp to work on veth pairs.
    '''
    Path('/proc/sys/net/ipv4/conf', ifname, 'accept_local').write_text('1')


@pytest_asyncio.fixture
async def veth_pair(
    dhcp_range: DHCPRangeConfig,
    async_context: TestContext[AsyncIPRoute],
    setns_context: SetNSContext,
) -> AsyncGenerator[VethPair, None]:
    '''Fixture that creates & removes a temporary veth pair.'''
    base_ifname = uifname()
    server_ifname = f'{base_ifname}-srv'
    client_ifname = f'{base_ifname}-cli'
    try:
        await async_context.ipr.link(
            'add', ifname=server_ifname, kind="veth", peer=client_ifname
        )
        srv_id = (await async_context.ipr.link_lookup(ifname=server_ifname))[0]
        cli_id = (await async_context.ipr.link_lookup(ifname=client_ifname))[0]
        await async_context.ipr.addr(
            'add',
            index=srv_id,
            address=str(dhcp_range.router),
            prefixlen=24,  # FIXME
        )
        await async_context.ipr.link("set", index=srv_id, state="up")
        await async_context.ipr.link("set", index=cli_id, state="up")
        accept_local(server_ifname)
        accept_local(client_ifname)
        yield VethPair(
            server=server_ifname,
            client=client_ifname,
            server_idx=srv_id,
            client_idx=cli_id,
        )
    finally:
        await async_context.ipr.link("del", index=srv_id)
