import pytest
from net_tools import address_exists, interface_exists, route_exists


@pytest.mark.asyncio
async def test_ensure_link_present(async_ipr, tmp_link_ifname, nsname):
    await async_ipr.ensure(
        async_ipr.link,
        present=True,
        ifname=tmp_link_ifname,
        kind='dummy',
        state='up',
    )
    assert interface_exists(tmp_link_ifname, netns=nsname)
    await async_ipr.ensure(
        async_ipr.link,
        present=True,
        ifname=tmp_link_ifname,
        kind='dummy',
        state='up',
    )


@pytest.mark.asyncio
async def test_ensure_link_absent(async_ipr, nsname, test_link_ifname):
    await async_ipr.ensure(
        async_ipr.link, present=False, ifname=test_link_ifname
    )
    assert not interface_exists(test_link_ifname, netns=nsname)
    await async_ipr.ensure(
        async_ipr.link, present=False, ifname=test_link_ifname
    )


@pytest.mark.asyncio
async def test_ensure_address_exists(
    async_ipr, nsname, test_link_index, test_link_ifname
):
    await async_ipr.ensure(
        async_ipr.addr,
        present=True,
        index=test_link_index,
        address='192.168.145.150/24',
    )
    assert address_exists('192.168.145.150', test_link_ifname, netns=nsname)
    await async_ipr.ensure(
        async_ipr.addr,
        present=True,
        index=test_link_index,
        address='192.168.145.150/24',
    )


@pytest.mark.asyncio
async def test_ensure_address_absent(
    async_ipr, nsname, test_link_index, test_link_ifname
):
    await async_ipr.ensure(
        async_ipr.addr,
        present=False,
        index=test_link_index,
        address='192.168.145.150/24',
    )
    assert not address_exists(
        '192.168.145.150', test_link_ifname, netns=nsname
    )
    await async_ipr.ensure(
        async_ipr.addr,
        present=False,
        index=test_link_index,
        address='192.168.145.150/24',
    )


@pytest.mark.asyncio
async def test_ensure_route(async_ipr, nsname, tmp_link_ifname):
    link = await async_ipr.ensure(
        async_ipr.link,
        present=True,
        ifname=tmp_link_ifname,
        kind='dummy',
        state='up',
    )
    await async_ipr.ensure(
        async_ipr.addr, present=True, index=link, address='192.168.145.150/24'
    )
    await async_ipr.ensure(
        async_ipr.route,
        present=True,
        dst='10.20.30.0/24',
        gateway='192.168.145.151',
    )
    assert route_exists(dst='10.20.30.0/24', netns=nsname)
