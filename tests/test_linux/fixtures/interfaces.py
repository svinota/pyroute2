import random
from ipaddress import IPv4Address
from typing import AsyncGenerator, NamedTuple

import pytest
import pytest_asyncio

from pyroute2.common import uifname
from pyroute2.iproute.linux import AsyncIPRoute


class DHCPRangeConfig(NamedTuple):
    start: IPv4Address
    end: IPv4Address
    router: IPv4Address
    netmask: IPv4Address


@pytest.fixture
def dhcp_range() -> DHCPRangeConfig:
    '''An IPv4 DHCP range configuration.'''
    rangeidx = random.randint(1, 254)
    return DHCPRangeConfig(
        start=IPv4Address(f'10.{rangeidx}.0.10'),
        end=IPv4Address(f'10.{rangeidx}.0.20'),
        router=IPv4Address(f'10.{rangeidx}.0.1'),
        netmask=IPv4Address('255.255.255.0'),
    )


class VethPair(NamedTuple):
    '''A pair of veth interfaces.'''

    server: str
    client: str


@pytest_asyncio.fixture
async def dummy_iface():
    '''Fixture that creates & removes a temporary dummy interface.'''
    ifname = uifname()
    async with AsyncIPRoute() as ipr:
        try:
            await ipr.link('add', ifname=ifname, kind='dummy', state='up')
            (idx,) = await ipr.link_lookup(ifname=ifname)
            yield idx, ifname
        finally:
            await ipr.link('del', index=idx)


@pytest_asyncio.fixture
async def veth_pair(
    dhcp_range: DHCPRangeConfig,
) -> AsyncGenerator[VethPair, None]:
    '''Fixture that creates & removes a temporary veth pair.'''
    # TODO: use AsyncIPRouteContext
    base_ifname = uifname()
    server_ifname = f'{base_ifname}-srv'
    client_ifname = f'{base_ifname}-cli'
    async with AsyncIPRoute() as ipr:
        try:
            await ipr.link(
                'add', ifname=server_ifname, kind="veth", peer=client_ifname
            )
            srv_id = (await ipr.link_lookup(ifname=server_ifname))[0]
            cli_id = (await ipr.link_lookup(ifname=client_ifname))[0]
            await ipr.addr(
                'add',
                index=srv_id,
                # TODO: handle IPv4Address in pyroute2 ?
                address=str(dhcp_range.router),
                prefixlen=24,  # FIXME
            )
            await ipr.link("set", index=srv_id, state="up")
            await ipr.link("set", index=cli_id, state="up")
            yield VethPair(server_ifname, client_ifname)
        finally:
            await ipr.link("del", index=srv_id)
