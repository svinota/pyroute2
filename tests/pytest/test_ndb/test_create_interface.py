from pyroute2 import NetlinkError
from pr2test.tools import address_exists
from pr2test.tools import interface_exists


def test_context_manager(local_ctx):

    ifname = local_ctx.ifname
    address = '00:11:22:36:47:58'
    spec = local_ctx.getspec(ifname=ifname, kind='dummy')
    ndb = local_ctx.ndb

    ifobj = ndb.interfaces.create(**spec)

    with ifobj:
        pass

    assert interface_exists(ifname, state='down')

    with ifobj:
        ifobj['state'] = 'up'
        ifobj['address'] = address

    spec = local_ctx.getspec(ifname=ifname)

    assert interface_exists(ifname, address=address, state='up')

    with ifobj:
        ifobj.remove()

    assert not interface_exists(ifname)


def test_fail(local_ctx):

    ifname = local_ctx.ifname
    kind = local_ctx.ifname
    spec = local_ctx.getspec(ifname=ifname, kind=kind)
    ndb = local_ctx.ndb

    ifobj = ndb.interfaces.create(**spec)

    save = dict(ifobj)

    try:
        ifobj.commit()
    except NetlinkError as e:
        assert e.code == 95  # Operation not supported

    assert save == dict(ifobj)
    assert ifobj.state == 'invalid'
    assert not interface_exists(ifname)


def test_veth_simple(local_ctx):
    ifname = local_ctx.ifname
    peername = local_ctx.ifname
    spec = local_ctx.getspec(ifname=ifname,
                             peer=peername,
                             kind='veth')
    ndb = local_ctx.ndb

    ndb.interfaces.create(**spec).commit()

    spec_ifl = local_ctx.getspec(ifname=ifname)
    spec_pl = local_ctx.getspec(ifname=peername)

    iflink = ndb.interfaces[spec_ifl]['link']
    plink = ndb.interfaces[spec_pl]['link']

    assert iflink == ndb.interfaces[spec_pl]['index']
    assert plink == ndb.interfaces[spec_ifl]['index']
    assert interface_exists(ifname)
    assert interface_exists(peername)

    ndb.interfaces[spec_ifl].remove().commit()

    assert not interface_exists(ifname)
    assert not interface_exists(peername)


def test_veth_spec(local_ctx):
    ifname = local_ctx.ifname
    peername = local_ctx.ifname
    nsname = local_ctx.nsname
    ndb = local_ctx.ndb

    ndb.sources.add(netns=nsname)

    spec = local_ctx.getspec(**{'ifname': ifname,
                                'kind': 'veth',
                                'peer': {'ifname': peername,
                                         'address': '00:11:22:33:44:55',
                                         'net_ns_fd': nsname}})
    ndb.interfaces.create(**spec).commit()
    ndb.interfaces.wait(target=nsname, ifname=peername)

    iflink = ndb.interfaces[local_ctx.getspec(ifname=ifname)]['link']
    plink = ndb.interfaces[{'target': nsname,
                            'ifname': peername}]['link']

    assert iflink == ndb.interfaces[{'target': nsname,
                                     'ifname': peername}]['index']
    assert plink == ndb.interfaces[local_ctx.getspec(ifname=ifname)]['index']
    assert interface_exists(ifname)
    assert interface_exists(peername, nsname)
    assert not interface_exists(ifname, nsname)
    assert not interface_exists(peername)

    ndb.interfaces[local_ctx.getspec(ifname=ifname)].remove().commit()

    assert not interface_exists(ifname)
    assert not interface_exists(ifname, nsname)
    assert not interface_exists(peername)
    assert not interface_exists(peername, nsname)

    ndb.sources.remove(nsname)


def test_dummy(local_ctx):

    ifname = local_ctx.ifname
    spec = local_ctx.getspec(ifname=ifname,
                             kind='dummy',
                             address='00:11:22:33:44:55')
    ndb = local_ctx.ndb
    ndb.interfaces.create(**spec).commit()
    assert interface_exists(ifname, address='00:11:22:33:44:55')


def test_bridge(local_ctx):

    bridge = local_ctx.ifname
    brport = local_ctx.ifname
    spec_br = local_ctx.getspec(ifname=bridge, kind='bridge')
    spec_pt = local_ctx.getspec(ifname=brport, kind='dummy')
    ndb = local_ctx.ndb

    (ndb
     .interfaces
     .create(**spec_br)
     .commit())
    (ndb
     .interfaces
     .create(**spec_pt)
     .set('master', ndb.interfaces[spec_br]['index'])
     .commit())

    assert interface_exists(bridge)
    assert interface_exists(brport, master=ndb.interfaces[spec_br]['index'])


def test_vrf(local_ctx):
    vrf = local_ctx.ifname
    spec = local_ctx.getspec(ifname=vrf, kind='vrf')
    (local_ctx
     .ndb
     .interfaces
     .create(**spec)
     .set('vrf_table', 42)
     .commit())
    assert interface_exists(vrf)


def test_vlan(local_ctx):
    host = local_ctx.ifname
    vlan = local_ctx.ifname
    spec_host = local_ctx.getspec(ifname=host, kind='dummy')
    spec_vlan = local_ctx.getspec(ifname=vlan, kind='vlan')
    (local_ctx
     .ndb
     .interfaces
     .create(**spec_host)
     .commit())
    (local_ctx
     .ndb
     .interfaces
     .create(**spec_vlan)
     .set('link', local_ctx.ndb.interfaces[spec_host]['index'])
     .set('vlan_id', 101)
     .commit())
    assert interface_exists(vlan)


def test_vxlan(local_ctx):
    host = local_ctx.ifname
    vxlan = local_ctx.ifname
    spec_host = local_ctx.getspec(ifname=host, kind='dummy')
    spec_vxlan = local_ctx.getspec(ifname=vxlan, kind='vxlan')
    (local_ctx
     .ndb
     .interfaces
     .create(**spec_host)
     .commit())
    (local_ctx
     .ndb
     .interfaces
     .create(**spec_vxlan)
     .set('vxlan_link', local_ctx.ndb.interfaces[spec_host]['index'])
     .set('vxlan_id', 101)
     .set('vxlan_group', '239.1.1.1')
     .set('vxlan_ttl', 16)
     .commit())
    assert interface_exists(vxlan)


def test_basic_address(local_ctx):

    ifaddr = local_ctx.ifaddr
    ifname = local_ctx.ifname
    spec_if = local_ctx.getspec(ifname=ifname, kind='dummy', state='up')
    i = (local_ctx
         .ndb
         .interfaces
         .create(**spec_if))
    i.commit()

    spec_ad = local_ctx.getspec(index=i['index'], address=ifaddr, prefixlen=24)
    a = (local_ctx
         .ndb
         .addresses
         .create(**spec_ad))
    a.commit()
    assert interface_exists(ifname)
    assert address_exists(ifname, address=ifaddr)
