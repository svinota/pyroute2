import pytest
from pr2test.tools import interface_exists


@pytest.mark.asyncio
async def test_link_dump(async_ipr):
    async for link in await async_ipr.link('dump'):
        assert link.get('index') > 0
        assert 1 < len(link.get('ifname')) < 16


async def util_link_add(async_ipr):
    ifname = async_ipr.register_temporary_ifname()
    await async_ipr.link('add', ifname=ifname, kind='dummy', state='up')
    assert interface_exists(ifname)
    return ifname


@pytest.mark.asyncio
async def test_link_add(async_ipr):
    await util_link_add(async_ipr)


@pytest.mark.asyncio
async def test_link_get(async_ipr):
    ifname = await util_link_add(async_ipr)
    (link,) = await async_ipr.link('get', ifname=ifname)
    assert link.get('state') == 'up'
    assert link.get('index') > 1
    assert link.get('ifname') == ifname
    assert link.get(('linkinfo', 'kind')) == 'dummy'


@pytest.mark.asyncio
async def test_link_del_by_index(async_ipr):
    ifname = await util_link_add(async_ipr)
    (link,) = await async_ipr.link('get', ifname=ifname)
    await async_ipr.link('del', index=link['index'])
    assert not interface_exists(ifname)


@pytest.mark.asyncio
async def test_link_del_by_name(async_ipr):
    ifname = await util_link_add(async_ipr)
    await async_ipr.link('del', ifname=ifname)
    assert not interface_exists(ifname)
