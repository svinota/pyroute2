import pytest
from net_tools import vlandb_exists

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


@pytest.mark.parametrize(
    'vid,state,check',
    ((101, 1, "listening"), (101, 2, "learning"), (101, 3, "forwarding")),
)
@pytest.mark.asyncio
async def test_vlan_set_state(async_ipr, vid, state, check):
    (bridge,) = await async_ipr.ensure(
        async_ipr.link, ifname=uifname(), kind='bridge', state='up'
    )
    await async_ipr.vlan_filter(
        'add', index=bridge.get('index'), vlan_flags=2, vlan_info={'vid': vid}
    )
    await async_ipr.vlandb(
        'set', ifindex=bridge.get('index'), vid=vid, state=state
    )
    assert vlandb_exists(
        bridge.get('ifname'), vid, check, netns=async_ipr.status['netns']
    )
