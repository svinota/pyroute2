import pytest
from pr2test.marks import require_root

pytestmark = [require_root()]


def test_vlan_filter_dump(context):
    ifname1 = context.new_ifname
    ifname2 = context.new_ifname
    context.ndb.interfaces.create(
        ifname=ifname1, kind='bridge', state='up'
    ).commit()
    context.ndb.interfaces.create(
        ifname=ifname2, kind='bridge', state='up'
    ).commit()
    assert len(tuple(context.ipr.get_vlans())) >= 2
    for name in (ifname1, ifname2):
        assert len(tuple(context.ipr.get_vlans(ifname=name))) == 1
        assert (
            tuple(context.ipr.get_vlans(ifname=name))[0].get_attr(
                'IFLA_IFNAME'
            )
        ) == name
        assert (
            tuple(context.ipr.get_vlans(ifname=name))[0].get_nested(
                'IFLA_AF_SPEC', 'IFLA_BRIDGE_VLAN_INFO'
            )
        )['vid'] == 1


@pytest.mark.parametrize(
    'arg_name,vid_spec,vid',
    (
        ('vlan_info', {'vid': 568}, 568),
        ('af_spec', {'attrs': [['IFLA_BRIDGE_VLAN_INFO', {'vid': 567}]]}, 567),
    ),
)
def _test_vlan_filter_add(context, arg_name, vid_spec, vid):
    ifname_port = context.new_ifname
    ifname_bridge = context.new_ifname
    port = context.ndb.interfaces.create(
        ifname=ifname_port, kind='dummy', state='up'
    ).commit()
    (
        context.ndb.interfaces.create(
            ifname=ifname_bridge, kind='bridge', state='up'
        )
        .add_port(ifname_port)
        .commit()
    )
    assert vid not in context.ndb.vlans
    spec = {'index': port['index'], arg_name: vid_spec}
    context.ipr.vlan_filter('add', **spec)
    assert context.ndb.vlans.wait(vid=vid, timeout=5)
    context.ipr.vlan_filter('del', **spec)
    assert context.ndb.vlans.wait(vid=vid, timeout=5, action='remove')
