import asyncio
import random
from ipaddress import IPv4Address, IPv4Interface
from typing import AsyncGenerator, NamedTuple

import pytest
import pytest_asyncio


class DHCPRangeConfig(NamedTuple):
    range_start: IPv4Address
    range_end: IPv4Address
    gw: IPv4Interface


async def ip(*args: str):
    '''Call `ip` in a subprocess.'''
    proc = await asyncio.create_subprocess_exec('ip', *args)
    stdout, stderr = await proc.communicate()
    assert proc.returncode == 0, stderr
    return stdout


@pytest.fixture
def dhcp_range() -> DHCPRangeConfig:
    ''' 'An IPv4 DHCP range configuration.'''
    rangeidx = random.randint(1, 254)
    return DHCPRangeConfig(
        range_start=IPv4Address(f'10.{rangeidx}.0.10'),
        range_end=IPv4Address(f'10.{rangeidx}.0.20'),
        gw=IPv4Interface(f'10.{rangeidx}.0.1/16'),
    )


class VethPair(NamedTuple):
    '''A pair of veth interfaces.'''

    server: str
    client: str


@pytest_asyncio.fixture
async def veth_pair(
    dhcp_range: DHCPRangeConfig,
) -> AsyncGenerator[VethPair, None]:
    '''Fixture that creates a temporary veth pair.'''
    # FIXME: use pyroute2
    # TODO: /proc/sys/net/ipv4/conf/{interface}/accept_local ?
    idx = random.randint(0, 999)
    server_ifname = f'dhcptest{idx}-srv'
    client_ifname = f'dhcptest{idx}-cli'
    try:
        await ip(
            'link',
            'add',
            server_ifname,
            'type',
            'veth',
            'peer',
            'name',
            client_ifname,
        )
        await ip('addr', 'add', str(dhcp_range.gw), 'dev', server_ifname)
        await ip('link', 'set', server_ifname, 'up')
        await ip('link', 'set', client_ifname, 'up')
        yield VethPair(server_ifname, client_ifname)
    finally:
        await ip('link', 'del', server_ifname)
