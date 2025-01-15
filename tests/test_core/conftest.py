import errno
import os

import pytest
import pytest_asyncio
from pr2test.plan9 import AsyncPlan9Context

from pyroute2 import AsyncIPRoute, IPRoute, NetlinkError, netns
from pyroute2.common import uifname


class AsyncIPRouteContext(AsyncIPRoute):
    def __init__(self, *argv, **kwarg):
        self.remove_netns_on_exit = False
        self.registry_ifname = set()
        if kwarg.get('netns') is True:
            kwarg['netns'] = uifname()
            kwarg['flags'] = os.O_CREAT
            self.remove_netns_on_exit = True
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
        await super().close(*argv, **kwarg)
        if self.remove_netns_on_exit:
            netns.remove(self.status['netns'])


class SyncIPRouteContext(IPRoute):
    def __init__(self, *argv, **kwarg):
        self.remove_netns_on_exit = False
        self.registry_ifname = set()
        if kwarg.get('netns') is True:
            kwarg['netns'] = uifname()
            kwarg['flags'] = os.O_CREAT
            self.remove_netns_on_exit = True
        super().__init__(*argv, **kwarg)

    def register_temporary_ifname(self, ifname=None):
        ifname = ifname if ifname is not None else uifname()
        self.registry_ifname.add(ifname)
        return ifname

    def register_temporary_netns(self, netns=None):
        netns = netns if netns is not None else uifname()
        self.registry_netns.add(netns)

    def close(self, *argv, **kwarg):
        for ifname in self.registry_ifname:
            try:
                self.link('del', ifname=ifname)
            except NetlinkError as e:
                if e.code != errno.ENODEV:
                    raise
        super().close(*argv, **kwarg)
        if self.remove_netns_on_exit:
            netns.remove(self.status['netns'])


@pytest_asyncio.fixture
async def p9(request, tmpdir):
    ctx = AsyncPlan9Context()
    await ctx.ensure_client()
    yield ctx
    await ctx.close()


@pytest_asyncio.fixture
async def async_ipr(request, tmpdir):
    kwarg = getattr(request, 'param', {})
    async with AsyncIPRouteContext(**kwarg) as ctx:
        yield ctx


@pytest.fixture
def sync_ipr(request, tmpdir):
    kwarg = getattr(request, 'param', {})
    with SyncIPRouteContext(**kwarg) as ctx:
        yield ctx
