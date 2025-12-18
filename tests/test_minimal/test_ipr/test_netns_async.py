import pytest

from pyroute2.netns import getnsfd


@pytest.mark.asyncio
async def test_set_netnsid_fd(async_ipr, nsname):
    fd = getnsfd(nsname)
    await async_ipr.set_netnsid(fd=fd, nsid=42)
    assert (await async_ipr.get_netnsid(fd=fd))['nsid'] == 42
