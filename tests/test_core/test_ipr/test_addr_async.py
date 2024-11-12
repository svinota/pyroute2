import re

import pytest
from pr2test.tools import address_exists, interface_exists

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


async def util_link_add(async_ipr):
    ifname = async_ipr.register_temporary_ifname()
    await async_ipr.link('add', ifname=ifname, kind='dummy', state='up')
    assert interface_exists(ifname)
    (link,) = await async_ipr.link('get', ifname=ifname)
    return ifname, link.get('index')


@pytest.mark.asyncio
async def test_addr_add(async_ipr):
    ifname, index = await util_link_add(async_ipr)
    await async_ipr.addr(
        'add', index=index, address='192.168.145.150', prefixlen=24
    )
    assert address_exists('192.168.145.150', ifname)
