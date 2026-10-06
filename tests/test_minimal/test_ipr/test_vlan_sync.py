import pytest
from net_tools import vlan_tunnel_exists, vlandb_exists

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


@pytest.mark.parametrize(
    'vid,tunid,tunnel',
    (
        (600, 600, {'vlan': 600, 'tunid': 600}),
        (100, 50000, {'vlan': 100, 'tunid': 50000}),
        (200, 16777215, {'vlan': 200, 'tunid': 16777215}),
        (
            '300-301',
            '16777214-16777215',
            {
                'vlan': 300,
                'vlanEnd': 301,
                'tunid': 16777214,
                'tunidEnd': 16777215,
            },
        ),
    ),
)
def test_vlan_tunnel_info(sync_ipr, vid, tunid, tunnel):
    # Tunnel ids are VXLAN VNIs, 24 bit, not bound by the VLAN id range.
    (bridge,) = sync_ipr.ensure(
        sync_ipr.link,
        ifname=uifname(),
        kind='bridge',
        br_vlan_filtering=1,
        state='up',
    )
    (vxlan,) = sync_ipr.ensure(
        sync_ipr.link,
        ifname=uifname(),
        kind='vxlan',
        vxlan_collect_metadata=1,
        vxlan_learning=0,
        master=bridge.get('index'),
        state='up',
    )
    sync_ipr.brport('set', index=vxlan.get('index'), vlan_tunnel=1)
    sync_ipr.vlan_filter(
        'add',
        index=vxlan.get('index'),
        vlan_info={'vid': vid},
        vlan_tunnel_info={'vid': vid, 'id': tunid},
    )
    assert vlan_tunnel_exists(
        vxlan.get('ifname'), tunnel, netns=sync_ipr.status['netns']
    )
