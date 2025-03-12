import time

import pytest

from pyroute2 import AsyncIPRoute, config, netns
from pyroute2.common import uifname


def fake_create(*argv, **kwarg):
    time.sleep(600)


@pytest.mark.asyncio
async def test_netns_timeout(monkeypatch):
    monkeypatch.setattr(config, 'default_create_socket_timeout', 1)
    monkeypatch.setattr(config, 'default_communicate_timeout', 0.3)
    monkeypatch.setattr(netns, '_create_socket_child', fake_create)

    ipr = AsyncIPRoute(netns=uifname())
    ts_start = time.time()
    with pytest.raises(TimeoutError):
        await ipr.setup_endpoint()
    assert time.time() - ts_start < 2
