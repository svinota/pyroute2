'''Fixtures only relevant for dhcp tests.'''

import json
import re
import socket
from typing import Awaitable, Callable, Optional

import pytest
from fixtures.dhcp_servers import lease_time  # noqa: F401
from fixtures.interfaces import VethPair

from pyroute2.common import uifname
from pyroute2.dhcp.client import ClientConfig
from pyroute2.fixtures.iproute import TestContext
from pyroute2.iproute.linux import AsyncIPRoute
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg


@pytest.fixture
def dhcp_client_host_name() -> str:
    '''The hostname option sent in dhcp tests.'''
    return f'test-hostname-{uifname()}'


@pytest.fixture
def dhcp_client_vendor_id() -> str:
    '''The vendor id option sent in dhcp tests.'''
    return f'vendor-id-{uifname()}'


@pytest.fixture
def client_config(
    veth_pair: VethPair,
    dhcp_client_host_name: Optional[str],
    dhcp_client_vendor_id: Optional[str],
) -> ClientConfig:
    '''Fixture that returns a ClientConfig for the veth_pair.

    Signal handlers are disabled.
    '''
    return ClientConfig(
        interface=veth_pair.client,
        vendor_id=dhcp_client_vendor_id,
        host_name=dhcp_client_host_name,
        handle_signals=False,
    )


@pytest.fixture
def set_fixed_xid(monkeypatch: pytest.MonkeyPatch) -> Callable[[int], None]:
    '''Set a static value to use instead of randomly generated xids.'''

    def _set_fixed_xid(xid: int):
        monkeypatch.setattr(
            "pyroute2.dhcp.xids.random_xid_prefix", lambda: xid
        )

    return _set_fixed_xid


async def _get_ipv4_addrs(ipr: AsyncIPRoute, index: int) -> list[str]:
    return [
        i
        async for i in await ipr.addr(
            'dump', index=index, family=socket.AF_INET
        )
    ]


GetIPv4Addrs = Callable[[None], Awaitable[list[ifaddrmsg]]]


@pytest.fixture
def get_ipv4_addrs(async_context: TestContext[AsyncIPRoute]) -> GetIPv4Addrs:
    '''Callable fixture that returns the test interface's ipv4 addresses.'''

    async def _wrapped() -> list[str]:
        return await _get_ipv4_addrs(
            ipr=async_context.ipr, index=async_context.test_link.index
        )

    return _wrapped


GetIPv4AddrsFor = Callable[[int], Awaitable[list[ifaddrmsg]]]


@pytest.fixture
def get_ipv4_addrs_for(async_ipr: AsyncIPRoute) -> GetIPv4AddrsFor:
    '''Callable fixture that returns an interface's ipv4 addresses.'''

    async def _wrapped(index: int) -> list[str]:
        return await _get_ipv4_addrs(ipr=async_ipr, index=index)

    return _wrapped


def parse_stdout_leases(data: bytes) -> list[dict]:
    '''Parses leases written by the client on stdout.'''
    return [json.loads(i) for i in re.split(b'(?<=\n)(?=\\{\n)', data)]
