'''Fixtures only relevant for dhcp tests.'''

import socket
from typing import Awaitable, Callable

import pytest
from fixtures.interfaces import VethPair

from pyroute2.dhcp.client import ClientConfig
from pyroute2.fixtures.iproute import TestContext
from pyroute2.iproute.linux import AsyncIPRoute


@pytest.fixture
def client_config(veth_pair: VethPair) -> ClientConfig:
    '''Fixture that returns a ClientConfig for the veth_pair.'''
    return ClientConfig(interface=veth_pair.client)


@pytest.fixture
def set_fixed_xid(monkeypatch: pytest.MonkeyPatch) -> Callable[[int], None]:
    '''Set a static value to use instead of randomly generated xids.'''

    def _set_fixed_xid(xid: int):
        monkeypatch.setattr(
            "pyroute2.dhcp.xids.random_xid_prefix", lambda: xid
        )

    return _set_fixed_xid


@pytest.fixture
def get_ipv4_addrs(
    async_context: TestContext[AsyncIPRoute],
) -> Callable[[None], Awaitable[list[str]]]:
    '''Callable fixture that returns the test interface's addresses.'''

    async def _get_ipv4_addrs() -> list[str]:
        return [
            i
            async for i in await async_context.ipr.addr(
                'dump',
                index=async_context.test_link.index,
                family=socket.AF_INET,
            )
        ]

    return _get_ipv4_addrs
