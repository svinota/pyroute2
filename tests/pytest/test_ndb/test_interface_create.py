import pytest
from pr2test.context_manager import make_test_matrix, skip_if_not_supported
from pr2test.tools import address_exists, interface_exists

from pyroute2 import NetlinkError

test_matrix = make_test_matrix(
    targets=['local', 'netns'], dbs=['sqlite3/:memory:', 'postgres/pr2test']
)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_context_manager(context):

    ifname = context.new_ifname
    address = '00:11:22:36:47:58'
    spec = {'ifname': ifname, 'kind': 'dummy'}

    ifobj = context.ndb.interfaces.create(**spec)

    with ifobj:
        pass

    assert interface_exists(context.netns, ifname=ifname, state='down')

    with ifobj:
        ifobj['state'] = 'up'
        ifobj['address'] = address

    assert interface_exists(
        context.netns, ifname=ifname, address=address, state='up'
    )

    with ifobj:
        ifobj.remove()

    assert not interface_exists(context.netns, ifname=ifname)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_fail(context):

    ifname = context.new_ifname
    kind = context.new_ifname
    spec = {'ifname': ifname, 'kind': kind}
    ifobj = context.ndb.interfaces.create(**spec)
    save = dict(ifobj)

    try:
        ifobj.commit()
    except NetlinkError as e:
        assert e.code == 95  # Operation not supported

    assert save == dict(ifobj)
    assert ifobj.state == 'invalid'
    assert not interface_exists(context.netns, ifname=ifname)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_veth_simple(context):
    ifname = context.new_ifname
    peername = context.new_ifname
    spec = {'ifname': ifname, 'peer': peername, 'kind': 'veth'}

    context.ndb.interfaces.create(**spec).commit()

    spec_ifl = {'ifname': ifname}
    spec_pl = {'ifname': peername}

    iflink = context.ndb.interfaces[spec_ifl]['link']
    plink = context.ndb.interfaces[spec_pl]['link']

    assert iflink == context.ndb.interfaces[spec_pl]['index']
    assert plink == context.ndb.interfaces[spec_ifl]['index']
    assert interface_exists(context.netns, ifname=ifname)
    assert interface_exists(context.netns, ifname=peername)

    context.ndb.interfaces[spec_ifl].remove().commit()

    assert not interface_exists(context.netns, ifname=ifname)
    assert not interface_exists(context.netns, ifname=peername)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_veth_spec(context):
    ifname = context.new_ifname
    peername = context.new_ifname
    nsname = context.new_nsname

    context.ndb.sources.add(netns=nsname)

    spec = {
        'ifname': ifname,
        'kind': 'veth',
        'peer': {
            'ifname': peername,
            'address': '00:11:22:33:44:55',
            'net_ns_fd': nsname,
        },
    }
    (context.ndb.interfaces.create(**spec).commit())

    (context.ndb.interfaces.wait(target=nsname, ifname=peername))

    iflink = context.ndb.interfaces[{'ifname': ifname}]['link']
    plink = context.ndb.interfaces[{'target': nsname, 'ifname': peername}][
        'link'
    ]

    assert iflink == (
        context.ndb.interfaces[{'target': nsname, 'ifname': peername}]['index']
    )
    assert plink == (context.ndb.interfaces[{'ifname': ifname}]['index'])

    assert interface_exists(context.netns, ifname=ifname)
    assert interface_exists(nsname, ifname=peername)
    assert not interface_exists(nsname, ifname=ifname)
    assert not interface_exists(context.netns, ifname=peername)

    (context.ndb.interfaces[{'ifname': ifname}].remove().commit())

    assert not interface_exists(context.netns, ifname=ifname)
    assert not interface_exists(nsname, ifname=ifname)
    assert not interface_exists(context.netns, ifname=peername)
    assert not interface_exists(nsname, ifname=peername)

    context.ndb.sources.remove(nsname)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_dummy(context):

    ifname = context.new_ifname
    spec = {'ifname': ifname, 'kind': 'dummy', 'address': '00:11:22:33:44:55'}
    context.ndb.interfaces.create(**spec).commit()
    assert interface_exists(
        context.netns, ifname=ifname, address='00:11:22:33:44:55'
    )


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_bridge(context):

    bridge = context.new_ifname
    brport = context.new_ifname
    spec_br = {'ifname': bridge, 'kind': 'bridge'}
    spec_pt = {'ifname': brport, 'kind': 'dummy'}

    (context.ndb.interfaces.create(**spec_br).commit())

    (
        context.ndb.interfaces.create(**spec_pt)
        .set('master', context.ndb.interfaces[spec_br]['index'])
        .commit()
    )

    assert interface_exists(context.netns, ifname=bridge)
    assert interface_exists(
        context.netns,
        ifname=brport,
        master=context.ndb.interfaces[spec_br]['index'],
    )


@pytest.mark.parametrize('context', test_matrix, indirect=True)
@skip_if_not_supported
def test_vrf(context):
    vrf = context.new_ifname
    spec = {'ifname': vrf, 'kind': 'vrf'}
    (context.ndb.interfaces.create(**spec).set('vrf_table', 42).commit())
    assert interface_exists(context.netns, ifname=vrf)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_vlan(context):
    host = context.new_ifname
    vlan = context.new_ifname
    spec_host = {'ifname': host, 'kind': 'dummy'}
    spec_vlan = {'ifname': vlan, 'kind': 'vlan'}
    (context.ndb.interfaces.create(**spec_host).commit())
    (
        context.ndb.interfaces.create(**spec_vlan)
        .set('link', context.ndb.interfaces[spec_host]['index'])
        .set('vlan_id', 101)
        .commit()
    )
    assert interface_exists(context.netns, ifname=vlan)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_vxlan(context):
    host = context.new_ifname
    vxlan = context.new_ifname
    spec_host = {'ifname': host, 'kind': 'dummy'}
    spec_vxlan = {'ifname': vxlan, 'kind': 'vxlan'}
    (context.ndb.interfaces.create(**spec_host).commit())
    (
        context.ndb.interfaces.create(**spec_vxlan)
        .set('vxlan_link', context.ndb.interfaces[spec_host]['index'])
        .set('vxlan_id', 101)
        .set('vxlan_group', '239.1.1.1')
        .set('vxlan_ttl', 16)
        .commit()
    )
    assert interface_exists(context.netns, ifname=vxlan)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_basic_address(context):

    ifaddr = context.new_ipaddr
    ifname = context.new_ifname
    spec_if = {'ifname': ifname, 'kind': 'dummy', 'state': 'up'}
    i = context.ndb.interfaces.create(**spec_if)
    i.commit()

    spec_ad = {'index': i['index'], 'address': ifaddr, 'prefixlen': 24}
    a = context.ndb.addresses.create(**spec_ad)
    a.commit()
    assert interface_exists(context.netns, ifname=ifname)
    assert address_exists(context.netns, ifname=ifname, address=ifaddr)
