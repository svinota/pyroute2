import gc
import weakref

import pytest

from pyroute2 import AsyncIPRoute, IPRoute


def get_event_loops():
    for obj in gc.get_objects():
        module = getattr(obj, '__module__', None)
        cls = getattr(obj, '__class__', None)
        if (
            isinstance(obj, weakref.ProxyType)
            or not isinstance(module, str)
            or not module.startswith('asyncio')
            or not cls.__name__.endswith('EventLoop')
            or not hasattr(obj, 'is_closed')
            or obj.is_closed()
        ):
            continue
        yield weakref.proxy(obj)


def test_event_loop_new():
    event_loops = list(get_event_loops())

    with IPRoute() as ipr:
        assert ipr.status['event_loop'] == 'new'
        assert len(list(ipr.get_links())) > 0

    gc.collect()
    assert len(event_loops) == len(list(get_event_loops()))


@pytest.mark.asyncio
async def test_event_loop_auto():
    event_loops = list(get_event_loops())

    async with AsyncIPRoute() as ipr:
        assert not ipr.event_loop.is_closed()
        assert ipr.status['event_loop'] == 'auto'
        assert len([x async for x in await ipr.get_links()]) > 0

    gc.collect()
    assert len(event_loops) == len(list(get_event_loops()))


@pytest.mark.asyncio
async def test_sync_fail_in_async_context():
    # sync IPRoute must fail in the async context
    with pytest.raises(RuntimeError):
        IPRoute()
