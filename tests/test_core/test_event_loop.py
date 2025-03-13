import asyncio
import errno
import gc
import threading
import traceback
import weakref

import pytest

from pyroute2 import AsyncIPRoute, IPRoute


def get_event_loops():
    for obj in gc.get_objects():
        try:
            module = getattr(obj, '__module__', None)
            cls = getattr(obj, '__class__', None)
        except ReferenceError:
            continue
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


def diff_event_loops(state=0):
    return len(list(get_event_loops())) - state


def threading_target_run(func_list, exc, ret):
    for func in func_list:
        try:
            ret.append(func())
        except Exception as e:
            e.tb = traceback.format_exc()
            ret.append(e)
            exc.append(e)


def test_event_loop_new():
    event_loops = list(get_event_loops())

    with IPRoute() as ipr:
        assert ipr.status['event_loop'] == 'new'
        assert len(list(ipr.get_links())) > 0

    gc.collect()
    assert len(event_loops) >= len(list(get_event_loops()))


def test_event_loop_count():
    state = diff_event_loops()
    ipr = IPRoute()
    assert diff_event_loops(state) == 1
    assert len(list(ipr.get_links())) > 0
    assert diff_event_loops(state) == 1
    ipr.close()
    assert diff_event_loops(state) == 0


def test_threading_close_noop():
    state = diff_event_loops()
    ipr = IPRoute()
    exc = []
    ret = []
    tt = threading.Thread(
        target=threading_target_run,
        args=[
            [
                lambda: diff_event_loops(state),
                lambda: ipr.close(),
                lambda: diff_event_loops(state),
            ],
            exc,
            ret,
        ],
    )
    tt.start()
    tt.join()
    ipr.close()
    assert len(exc) == 0
    assert len(ret) == 3
    assert ret == [1, None, 1]
    assert diff_event_loops(state) == 0


def test_threading_close_op():
    state = diff_event_loops()
    ipr = IPRoute()
    exc = []
    ret = []
    tt = threading.Thread(
        target=threading_target_run,
        args=[
            [
                lambda: diff_event_loops(state),
                lambda: len(list(ipr.get_links())),
                lambda: diff_event_loops(state),
                lambda: ipr.close(),
                lambda: diff_event_loops(state),
            ],
            exc,
            ret,
        ],
    )
    tt.start()
    tt.join()
    ipr.close()
    assert len(exc) == 0
    assert len(ret) == 5
    assert ret[0] == 1
    assert ret[1] > 1
    assert ret[2] == 1
    assert ret[3] is None
    assert ret[4] == 1
    assert diff_event_loops(state) == 0


def test_threading_sync():
    event_loop = asyncio.new_event_loop()
    ipr = IPRoute(use_event_loop=event_loop)
    exc = []
    ret = []
    assert len(list(ipr.get_links())) > 1
    tt = threading.Thread(
        target=threading_target_run,
        args=[[lambda: list(ipr.get_links())], exc, ret],
    )
    tt.start()
    tt.join()
    assert len(exc) == 1
    assert isinstance(exc[0], RuntimeError)
    assert (
        exc[0].args[0]
        == 'Predefined event loop can not be used in another thread'
    )


def test_threading_bind():
    state = diff_event_loops()
    ipr = IPRoute()
    assert diff_event_loops(state) == 1
    ready_event = threading.Event()
    close_event = threading.Event()
    exc = []
    ret = []
    tt = threading.Thread(
        target=threading_target_run,
        args=[
            [
                lambda: ipr.bind(),
                lambda: diff_event_loops(state),
                lambda: ready_event.set(),
                lambda: close_event.wait(),
                lambda: [x for x in ipr.get()],
                lambda: diff_event_loops(state),
            ],
            exc,
            ret,
        ],
    )
    tt.start()
    ready_event.wait()
    ipr.close()
    close_event.set()
    tt.join()
    assert ret[1] == 2
    assert isinstance(ret[4], OSError)
    assert ret[4].errno == errno.EBADF
    assert ret[5] == 0


@pytest.mark.asyncio
async def test_event_loop_auto():
    event_loops = list(get_event_loops())

    async with AsyncIPRoute() as ipr:
        assert not ipr.event_loop.is_closed()
        assert ipr.status['event_loop'] == 'auto'
        assert len([x async for x in await ipr.get_links()]) > 0

    gc.collect()
    assert len(event_loops) >= len(list(get_event_loops()))


@pytest.mark.asyncio
async def test_sync_fail_in_async_context():
    # sync IPRoute must fail in the async context
    with pytest.raises(RuntimeError):
        IPRoute()
