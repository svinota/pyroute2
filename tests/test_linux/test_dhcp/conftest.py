'''Fixtures only relevant for dhcp tests.'''

import socket
from typing import Callable

import pytest
from fixtures.interfaces import VethPair

from pyroute2.dhcp.client import ClientConfig
from pyroute2.iproute.linux import AsyncIPRoute


@pytest.fixture
def client_config(veth_pair: VethPair) -> ClientConfig:
    '''Fixture that returns a ClientConfig for the veth_pair.'''
    return ClientConfig(interface=veth_pair.client)


@pytest.fixture
def set_fixed_xid(monkeypatch: pytest.MonkeyPatch) -> Callable[[int], None]:
    def _set_fixed_xid(xid: int):
        monkeypatch.setattr(
            "pyroute2.dhcp.xids.random_xid_prefix", lambda: xid
        )

    return _set_fixed_xid


async def ipv4_addrs(ifindex):
    '''Shortcut for `ipr.addr('dump')`.'''
    # FIXME: refactor into a fixture that depends on async_ipr
    # when the fixture refactoring will be done
    # or better, use a fixture from pyroute2 if it exists
    async with AsyncIPRoute() as ipr:
        return [
            i
            async for i in await ipr.addr(
                'dump', index=ifindex, family=socket.AF_INET
            )
        ]
