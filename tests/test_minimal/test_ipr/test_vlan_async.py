import pytest

from pyroute2.common import uifname


@pytest.mark.parametrize(
    'flags,option,check',
    (
        (1, 'entry', lambda x: x.get(('info', 'vid')) == 1),
        (2, 'global_options', lambda x: x.get('id') == 1),
    ),
)
@pytest.mark.asyncio
async def test_vlan_dumpdb(async_ipr, flags, option, check):
    await async_ipr.ensure(
        async_ipr.link, ifname=uifname(), kind='bridge', state='up'
    )
    async for response in await async_ipr.vlandb('dump', dump_flags=flags):
        for vlan in response.get_attrs(option):
            assert check(vlan)
        break
    else:
        raise Exception('no vlan info dumped')
