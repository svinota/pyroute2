from pr2test.marks import require_root

pytestmark = [require_root()]


def test_fdb_vxlan(context):
    ipaddr = context.new_ipaddr
    host_if = context.new_ifname
    vxlan_if = context.new_ifname

    context.ndb.interfaces.create(ifname=host_if, kind='dummy').commit()
    host_idx = context.ndb.interfaces[host_if]['index']
    (
        context.ndb.interfaces.create(
            ifname=vxlan_if, kind='vxlan', vxlan_link=host_idx, vxlan_id=500
        ).commit()
    )
    vxlan_idx = context.ndb.interfaces[vxlan_if]['index']

    # create FDB record
    l2 = '00:11:22:33:44:55'
    (
        context.ipr.fdb(
            'add', lladdr=l2, ifindex=vxlan_idx, vni=600, port=5678, dst=ipaddr
        )
    )
    # dump
    r = tuple(context.ipr.fdb('dump', ifindex=vxlan_idx, lladdr=l2))
    assert len(r) == 1
    assert r[0]['ifindex'] == vxlan_idx
    assert r[0].get_attr('NDA_LLADDR') == l2
    assert r[0].get_attr('NDA_DST') == ipaddr
    assert r[0].get_attr('NDA_PORT') == 5678
    assert r[0].get_attr('NDA_VNI') == 600


def test_fdb_bridge_simple(context):

    ifname = context.new_ifname
    (
        context.ndb.interfaces.create(
            ifname=ifname, kind='bridge', state='up'
        ).commit()
    )
    idx = context.ndb.interfaces[ifname]['index']
    # create FDB record
    l2 = '00:11:22:33:44:55'
    context.ipr.fdb('add', lladdr=l2, ifindex=idx)
    # dump FDB
    r = tuple(context.ipr.fdb('dump', ifindex=idx, lladdr=l2))
    # one vlan == 1, one w/o vlan
    assert len(r) == 2
    assert len(list(filter(lambda x: x['ifindex'] == idx, r))) == 2
    assert len(list(filter(lambda x: x.get_attr('NDA_VLAN'), r))) == 1
    assert len(list(filter(lambda x: x.get_attr('NDA_MASTER') == idx, r))) == 2
    assert len(list(filter(lambda x: x.get_attr('NDA_LLADDR') == l2, r))) == 2
    r = tuple(context.ipr.fdb('dump', ifindex=idx, lladdr=l2, vlan=1))
    assert len(r) == 1
    assert r[0].get_attr('NDA_VLAN') == 1
    assert r[0].get_attr('NDA_MASTER') == idx
    assert r[0].get_attr('NDA_LLADDR') == l2
