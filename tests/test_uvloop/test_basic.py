import asyncio
import selectors

import pytest
import uvloop

from pyroute2 import IPRoute

uvloop.install()


def test_fail():
    with pytest.raises(ValueError):
        with IPRoute():
            pass


def test_basic():
    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)

    with IPRoute(use_event_loop=loop) as ipr:
        for link in ipr.link('dump'):
            assert link.get('index') > 0
