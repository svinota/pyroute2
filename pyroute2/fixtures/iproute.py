# pylint: disable=redefined-outer-name

import errno
from collections import namedtuple
from collections.abc import AsyncGenerator, Generator
from typing import Union

import pytest
import pytest_asyncio

from pyroute2 import netns
from pyroute2.common import uifname
from pyroute2.iproute.linux import AsyncIPRoute, IPRoute
from pyroute2.netlink.exceptions import NetlinkError

TestInterface = namedtuple('TestInterface', ('index', 'ifname'))


@pytest.fixture
def nsname() -> Generator[str]:
    '''Create a unique network namespace and yield its name.

    Remove the netns on exit.
    '''
    nsname = uifname()
    netns.create(nsname)
    with IPRoute(netns=nsname) as ipr:
        ipr.link('set', index=1, state='up')
        ipr.poll(ipr.addr, 'dump', address='127.0.0.1', timeout=5)
    yield nsname
    try:
        netns.remove(nsname)
    except OSError:
        pass


@pytest.fixture
def test_link(nsname: str) -> Generator[TestInterface]:
    '''Create a test interface in the test netns and yield TestInterface.

    Remove the interface on exit.
    '''
    ifname = uifname()
    with IPRoute(netns=nsname) as ipr:
        ipr.link('add', ifname=ifname, kind='dummy', state='up')
        (link,) = ipr.poll(ipr.link, 'dump', ifname=ifname, timeout=5)
        yield TestInterface(index=link.get('index'), ifname=link.get('ifname'))
        try:
            ipr.link('del', index=link.get('index'))
        except NetlinkError as e:
            if e.code != errno.ENODEV:
                raise


@pytest.fixture
def test_link_index(test_link: TestInterface) -> Generator[int]:
    '''Yield test interface index.'''
    yield test_link.index


@pytest.fixture
def test_link_ifname(test_link: TestInterface) -> Generator[str]:
    '''Yield test interface name.'''
    yield test_link.ifname


@pytest.fixture
def tmp_link_ifname(nsname: str) -> Generator[str]:
    '''Yield a temporary interface name.

    But don't create it. Try to remove on exit.
    '''
    ifname = uifname()
    with IPRoute(netns=nsname) as ipr:
        yield ifname
        try:
            (link,) = ipr.link('get', ifname=ifname)
            ipr.link('del', index=link.get('index'))
        except NetlinkError as e:
            if e.code != errno.ENODEV:
                raise


class TestContext:
    '''The test context.

    Provides convenient shortcuts and data.
    '''

    def __init__(
        self, ipr: Union[IPRoute, AsyncIPRoute], test_link: TestInterface
    ):
        self._ipr = ipr
        self._test_link = test_link

    @property
    def ipr(self) -> Union[IPRoute, AsyncIPRoute]:
        '''Return RTNL API instance, either sync or async.'''
        return self._ipr

    @property
    def test_link(self) -> TestInterface:
        '''Return TestInterface instance.'''
        return self._test_link

    @property
    def netns(self) -> str:
        '''Return the network namespace name.'''
        return self.ipr.status['netns']


@pytest_asyncio.fixture
async def async_ipr(request, nsname: str) -> AsyncGenerator[AsyncIPRoute]:
    kwarg = getattr(request, 'param', {})
    async with AsyncIPRoute(netns=nsname, **kwarg) as ipr:
        yield ipr


@pytest.fixture
def sync_ipr(request, nsname: str) -> Generator[IPRoute]:
    kwarg = getattr(request, 'param', {})
    with IPRoute(netns=nsname, **kwarg) as ipr:
        yield ipr


@pytest_asyncio.fixture
async def async_context(
    async_ipr: AsyncIPRoute, test_link: TestInterface
) -> AsyncGenerator[TestContext]:
    yield TestContext(async_ipr, test_link)


@pytest.fixture
def sync_context(
    sync_ipr: IPRoute, test_link: TestInterface
) -> Generator[TestContext]:
    yield TestContext(sync_ipr, test_link)
