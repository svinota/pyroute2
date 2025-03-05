import time

import pytest

from pyroute2 import AsyncIPRoute, config, netns
from pyroute2.common import uifname


@pytest.mark.asyncio
async def test_netns_timeout(monkeypatch):
    monkeypatch.setattr(config, 'default_create_socket_timeout', 1)
    monkeypatch.setattr(config, 'default_communicate_timeout', 0.3)
    monkeypatch.setattr(
        netns, '_create_socket_child', lambda *_, **__: time.sleep(600)
    )

    ipr = AsyncIPRoute(netns=uifname())
    with pytest.raises(TimeoutError):
        await ipr.ensure_socket()
