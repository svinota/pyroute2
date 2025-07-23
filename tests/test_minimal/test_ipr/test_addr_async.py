import re

import pytest
from net_tools import address_exists

ip4v6 = re.compile('^[.:0-9a-f]*$')


@pytest.mark.asyncio
async def test_addr_dump(async_ipr):
    async for addr in await async_ipr.addr('dump'):
        index = addr.get('index')
        address = addr.get('address', '')
        prefixlen = addr.get('prefixlen')
        assert index > 0
        assert ip4v6.match(address)
        assert prefixlen > 0


@pytest.mark.asyncio
async def test_addr_add(async_ipr, test_link_ifname, test_link_index, nsname):
    await async_ipr.addr(
        'add', index=test_link_index, address='192.168.145.150', prefixlen=24
    )
    assert address_exists('192.168.145.150', test_link_ifname, netns=nsname)


@pytest.mark.parametrize(
    'request_info,assert_info',
    (
        ({'preferred': 99}, {'preferred': 99}),
        ({'preferred_lft': 109}, {'preferred': 109}),
        ({'valid': 119, 'preferred': 100}, {'valid': 119}),
        ({'valid_lft': 129, 'preferred': 100}, {'valid': 129}),
    ),
)
@pytest.mark.asyncio
async def test_addr_cacheinfo(
    async_ipr,
    test_link_ifname,
    test_link_index,
    nsname,
    request_info,
    assert_info,
):
    await async_ipr.addr(
        'add',
        index=test_link_index,
        address='2001:db8::5678',
        mask=128,
        **request_info,
    )
    assert address_exists('2001:db8::5678', netns=nsname, **assert_info)
