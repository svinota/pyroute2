import errno

import pytest
import pytest_asyncio
from pr2test.plan9 import AsyncPlan9Context

from pyroute2 import AsyncIPRoute, IPRoute, NetlinkError, netns
from pyroute2.common import uifname


@pytest_asyncio.fixture
async def p9(request, tmpdir):
    ctx = AsyncPlan9Context()
    await ctx.ensure_session()
    yield ctx
    await ctx.close()


@pytest.fixture
def nsname():
    ns = uifname()
    netns.create(ns)
    with IPRoute(netns=ns) as ipr:
        ipr.link('set', index=1, state='up')
        ipr.poll(ipr.addr, 'dump', address='127.0.0.1', timeout=5)
    yield ns
    try:
        netns.delete(ns)
    except Exception:
        pass


@pytest.fixture
def link(nsname):
    ifname = uifname()
    with IPRoute(netns=nsname) as ipr:
        ipr.link('add', ifname=ifname, kind='dummy', state='up')
        (link,) = ipr.poll(ipr.link, 'dump', ifname=ifname, timeout=5)
        yield link
        try:
            ipr.link('del', index=link.get('index'))
        except NetlinkError as e:
            if e.code != errno.ENODEV:
                raise


@pytest.fixture
def index(link):
    yield link.get('index')


@pytest.fixture
def ifname(link):
    yield link.get('ifname')


@pytest.fixture
def tmp_link(nsname):
    ifname = uifname()
    with IPRoute(netns=nsname) as ipr:
        yield ifname
        try:
            (link,) = ipr.link('get', ifname=ifname)
            ipr.link('del', index=link.get('index'))
        except NetlinkError as e:
            if e.code != errno.ENODEV:
                raise


@pytest_asyncio.fixture
async def async_ipr(nsname, request):
    kwarg = getattr(request, 'param', {})
    async with AsyncIPRoute(netns=nsname, **kwarg) as ctx:
        yield ctx


@pytest.fixture
def sync_ipr(nsname, request):
    kwarg = getattr(request, 'param', {})
    with IPRoute(netns=nsname, **kwarg) as ctx:
        yield ctx
