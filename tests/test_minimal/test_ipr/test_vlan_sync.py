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
def test_vlan_dumpdb(sync_ipr, flags, option, check):
    sync_ipr.ensure(sync_ipr.link, ifname=uifname(), kind='bridge', state='up')
    for response in sync_ipr.vlandb('dump', dump_flags=flags):
        for vlan in response.get_attrs(option):
            assert check(vlan)
        break
    else:
        raise Exception('no vlan info dumped')


@pytest.mark.parametrize(
    'vid,state,check',
    ((101, 1, "listening"), (101, 2, "learning"), (101, 3, "forwarding")),
)
def test_vlan_set_state(sync_ipr, vid, state, check):
    (bridge,) = sync_ipr.ensure(
        sync_ipr.link, ifname=uifname(), kind='bridge', state='up'
    )
    sync_ipr.vlan_filter(
        'add', index=bridge.get('index'), vlan_flags=2, vlan_info={'vid': vid}
    )
    sync_ipr.vlandb('set', ifindex=bridge.get('index'), vid=vid, state=state)
    assert vlandb_exists(
        bridge.get('ifname'), vid, check, netns=sync_ipr.status['netns']
    )
