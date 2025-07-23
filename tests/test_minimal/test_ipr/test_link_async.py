import pytest
from net_tools import interface_exists


@pytest.mark.asyncio
async def test_link_dump(async_ipr):
    async for link in await async_ipr.link('dump'):
        assert link.get('index') > 0
        assert 1 < len(link.get('ifname')) < 16


@pytest.mark.asyncio
async def test_link_add(async_ipr, tmp_link_ifname, nsname):
    await async_ipr.link(
        'add', ifname=tmp_link_ifname, kind='dummy', state='up'
    )
    assert interface_exists(tmp_link_ifname, netns=nsname)


@pytest.mark.asyncio
async def test_link_get(async_ipr, test_link_ifname):
    (link,) = await async_ipr.link('get', ifname=test_link_ifname)
    assert link.get('state') == 'up'
    assert link.get('index') > 1
    assert link.get('ifname') == test_link_ifname
    assert link.get(('linkinfo', 'kind')) == 'dummy'


@pytest.mark.asyncio
async def test_link_del_by_index(
    async_ipr, test_link_ifname, test_link_index, nsname
):
    (link,) = await async_ipr.link('get', ifname=test_link_ifname)
    await async_ipr.link('del', index=test_link_index)
    assert not interface_exists(test_link_ifname, netns=nsname)


@pytest.mark.asyncio
async def test_link_del_by_name(async_ipr, test_link_ifname, nsname):
    await async_ipr.link('del', ifname=test_link_ifname)
    assert not interface_exists(test_link_ifname, netns=nsname)
