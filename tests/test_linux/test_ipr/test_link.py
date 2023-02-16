import pytest
from pr2test.context_manager import make_test_matrix, skip_if_not_supported
from pr2test.marks import require_root

from pyroute2 import NetlinkError
from pyroute2.netlink.rtnl.ifinfmsg import IFF_NOARP

pytestmark = [require_root()]

test_matrix = make_test_matrix(targets=['local', 'netns'])


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_updown_link(context):
    index, ifname = context.default_interface

    context.ipr.link('set', index=index, state='up')
    assert context.ipr.get_links(ifname=ifname)[0]['flags'] & 1
    context.ipr.link('set', index=index, state='down')
    assert not (context.ipr.get_links(ifname=ifname)[0]['flags'] & 1)


@skip_if_not_supported
@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_link_altname_lookup(context):
    altname = context.new_ifname
    index, ifname = context.default_interface
    context.ipr.link('property_add', index=index, altname=altname)
    assert len(context.ipr.link('get', altname=altname)) == 1
    assert context.ipr.link_lookup(ifname=ifname) == [index]
    assert context.ipr.link_lookup(altname=altname) == [index]


@skip_if_not_supported
@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_link_altname(context):
    altname1 = context.new_ifname
    altname2 = context.new_ifname
    weird_name = "test_with_a_very_long_string" "_and_♄⚕⚚_utf8_symbol"
    index, ifname = context.default_interface

    for name in (altname1, altname2, weird_name):
        with pytest.raises(NetlinkError):
            context.ipr.link("get", altname=name)

    context.ipr.link("property_add", index=index, altname=[altname1, altname2])
    assert len(context.ipr.link("get", altname=altname1)) == 1
    assert len(context.ipr.link("get", altname=altname2)) == 1

    context.ipr.link("property_del", index=index, altname=[altname1, altname2])

    for name in (altname1, altname2):
        with pytest.raises(NetlinkError):
            context.ipr.link("get", altname=name)

    context.ipr.link("property_add", index=index, altname=weird_name)
    assert len(context.ipr.link("get", altname=weird_name)) == 1
    context.ipr.link("property_del", index=index, altname=weird_name)
    assert len(tuple(context.ipr.link("dump", altname=weird_name))) == 0
    with pytest.raises(NetlinkError):
        context.ipr.link("get", altname=weird_name)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_link_filter(context):
    links = tuple(context.ipr.link('dump', ifname='lo'))
    assert len(links) == 1
    assert links[0].get_attr('IFLA_IFNAME') == 'lo'


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_link_legacy_nla(context):
    index, ifname = context.default_interface
    new_ifname = context.new_ifname

    context.ipr.link('set', index=index, state='down')
    context.ipr.link('set', index=index, IFLA_IFNAME=new_ifname)
    assert context.ipr.link_lookup(ifname=new_ifname) == [index]

    context.ipr.link('set', index=index, ifname=ifname)
    assert context.ipr.link_lookup(ifname=ifname) == [index]


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_link_rename(context):
    index, ifname = context.default_interface
    new_ifname = context.new_ifname
    context.ndb.interfaces[ifname].set('state', 'down').commit()

    context.ipr.link('set', index=index, ifname=new_ifname)
    assert context.ipr.link_lookup(ifname=new_ifname) == [index]

    context.ipr.link('set', index=index, ifname=ifname)
    assert context.ipr.link_lookup(ifname=ifname) == [index]


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_link_arp_flag(context):
    index, _ = context.default_interface

    # by default dummy interface have NOARP set
    assert context.ipr.get_links(index)[0]['flags'] & IFF_NOARP

    context.ipr.link('set', index=index, arp=True)
    assert not context.ipr.get_links(index)[0]['flags'] & IFF_NOARP

    context.ipr.link('set', index=index, arp=False)
    assert context.ipr.get_links(index)[0]['flags'] & IFF_NOARP

    context.ipr.link('set', index=index, noarp=False)
    assert not context.ipr.get_links(index)[0]['flags'] & IFF_NOARP

    context.ipr.link('set', index=index, noarp=True)
    assert context.ipr.get_links(index)[0]['flags'] & IFF_NOARP


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_symbolic_flags_ifinfmsg(context):
    index, _ = context.default_interface

    context.ipr.link('set', index=index, flags=['IFF_UP'])
    iface = context.ipr.get_links(index)[0]
    assert iface['flags'] & 1
    assert 'IFF_UP' in iface.flags2names(iface['flags'])
    context.ipr.link('set', index=index, flags=['!IFF_UP'])
    assert not (context.ipr.get_links(index)[0]['flags'] & 1)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_remove_link(context):
    index, ifname = context.default_interface
    context.ipr.link('del', index=index)
    assert len(context.ipr.link_lookup(ifname=ifname)) == 0
    assert len(context.ipr.link_lookup(index=index)) == 0


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_brport_basic(context):

    bridge = context.new_ifname
    port = context.new_ifname

    context.ndb.interfaces.create(
        ifname=bridge, kind='bridge', state='up'
    ).commit()
    context.ndb.interfaces.create(
        ifname=port, kind='dummy', state='up'
    ).commit()

    context.ipr.link(
        'set',
        index=context.ndb.interfaces[port]['index'],
        master=context.ndb.interfaces[bridge]['index'],
    )

    context.ipr.brport(
        'set',
        index=context.ndb.interfaces[port]['index'],
        unicast_flood=0,
        cost=200,
        proxyarp=1,
    )

    port = tuple(
        context.ipr.brport('dump', index=context.ndb.interfaces[port]['index'])
    )[0]
    protinfo = port.get_attr('IFLA_PROTINFO')
    assert protinfo.get_attr('IFLA_BRPORT_COST') == 200
    assert protinfo.get_attr('IFLA_BRPORT_PROXYARP') == 1
    assert protinfo.get_attr('IFLA_BRPORT_UNICAST_FLOOD') == 0
