import errno
import sys

import pytest
import pytest_asyncio

print(sys.path)
from pr2test.plan9 import AsyncPlan9Context

from pyroute2 import AsyncIPRoute, IPRoute, NetlinkError
from pyroute2.common import uifname


class AsyncIPRouteContext(AsyncIPRoute):
    def __init__(self, *argv, **kwarg):
        self.registry_ifname = set()
        super().__init__(*argv, **kwarg)

    def register_temporary_ifname(self, ifname=None):
        ifname = ifname if ifname is not None else uifname()
        self.registry_ifname.add(ifname)
        return ifname

    async def close(self, *argv, **kwarg):
        for ifname in self.registry_ifname:
            try:
                await self.link('del', ifname=ifname)
            except NetlinkError as e:
                if e.code != errno.ENODEV:
                    raise


class SyncIPRouteContext(IPRoute):
    def __init__(self, *argv, **kwarg):
        self.registry_ifname = set()
        super().__init__(*argv, **kwarg)

    def register_temporary_ifname(self, ifname=None):
        ifname = ifname if ifname is not None else uifname()
        self.registry_ifname.add(ifname)
        return ifname

    def close(self, *argv, **kwarg):
        for ifname in self.registry_ifname:
            try:
                self.link('del', ifname=ifname)
            except NetlinkError as e:
                if e.code != errno.ENODEV:
                    raise


@pytest_asyncio.fixture
async def p9(request, tmpdir):
    ctx = AsyncPlan9Context()
    await ctx.ensure_client()
    yield ctx
    await ctx.close()


@pytest_asyncio.fixture
async def async_ipr(request, tmpdir):
    async with AsyncIPRouteContext() as ctx:
        yield ctx


@pytest.fixture
def sync_ipr(request, tmpdir):
    with SyncIPRouteContext() as ctx:
        yield ctx
