import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.marks import require_root
from pr2test.tools import address_exists, interface_exists, route_exists

pytestmark = [require_root()]

test_matrix = make_test_matrix(
    targets=['local', 'netns'], dbs=['sqlite3/:memory:', 'postgres/pr2test']
)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_create(context):
    ifname = context.new_ifname
    iface = context.ndb.interfaces.create(ifname=ifname, kind='dummy').commit()
    assert interface_exists(context.netns, ifname=ifname)
    iface.rollback()
    assert not interface_exists(context.netns, ifname=ifname)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_remove(context):
    ifname = context.new_ifname
    iface = context.ndb.interfaces.create(ifname=ifname, kind='dummy').commit()
    assert interface_exists(context.netns, ifname=ifname)
    iface.remove().commit()
    assert not interface_exists(context.netns, ifname=ifname)
    iface.rollback()
    assert interface_exists(context.netns, ifname=ifname)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_set(context):
    ifname = context.new_ifname
    (
        context.ndb.interfaces.create(
            ifname=ifname, kind='dummy', address='00:11:22:33:44:55'
        ).commit()
    )
    assert interface_exists(
        context.netns, ifname=ifname, address='00:11:22:33:44:55'
    )
    (
        context.ndb.interfaces[ifname]
        .set('address', '00:11:22:aa:aa:aa')
        .commit()
    )
    assert not interface_exists(
        context.netns, ifname=ifname, address='00:11:22:33:44:55'
    )
    assert interface_exists(
        context.netns, ifname=ifname, address='00:11:22:aa:aa:aa'
    )
    (context.ndb.interfaces[ifname].rollback())
    assert not interface_exists(
        context.netns, ifname=ifname, address='00:11:22:aa:aa:aa'
    )
    assert interface_exists(
        context.netns, ifname=ifname, address='00:11:22:33:44:55'
    )


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_simple_deps(context):
    ifname = context.new_ifname
    ipaddr = context.new_ipaddr
    router = context.new_ipaddr
    dst = str(context.ipnets[1].network)

    #
    # simple dummy interface with one address and
    # one dependent route
    #
    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy')
        .set('state', 'up')
        .add_ip(address=ipaddr, prefixlen=24)
        .commit()
    )

    (context.ndb.routes.create(dst=dst, dst_len=24, gateway=router).commit())

    # check everything is in place
    assert interface_exists(context.netns, ifname=ifname)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr)
    assert route_exists(context.netns, gateway=router, dst=dst, dst_len=24)

    # remove the interface
    iface = context.ndb.interfaces[ifname].remove().commit()

    # check there is no interface, no route
    assert not interface_exists(context.netns, ifname=ifname)
    assert not address_exists(context.netns, ifname=ifname, address=ipaddr)
    assert not route_exists(context.netns, gateway=router, dst=dst, dst_len=24)

    # revert the changes using the implicit last_save
    iface.rollback()

    assert interface_exists(context.netns, ifname=ifname)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr)
    assert route_exists(context.netns, gateway=router, dst=dst, dst_len=24)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_bridge_deps(context):
    if_br0 = context.new_ifname
    if_br0p0 = context.new_ifname
    if_br0p1 = context.new_ifname
    ifaddr1 = context.new_ipaddr
    ifaddr2 = context.new_ipaddr
    router = context.new_ipaddr
    dst = str(context.ipnets[1].network)

    with context.ndb.interfaces as i:
        i.create(ifname=if_br0p0, kind='dummy', state='up').commit()
        i.create(ifname=if_br0p1, kind='dummy', state='up').commit()
        (
            i.create(ifname=if_br0, kind='bridge', state='up')
            .add_port(if_br0p0)
            .add_port(if_br0p1)
            .add_ip(address=ifaddr1, prefixlen=24)
            .add_ip(address=ifaddr2, prefixlen=24)
            .commit()
        )

    (context.ndb.routes.create(dst=dst, dst_len=24, gateway=router).commit())

    assert interface_exists(context.netns, ifname=if_br0)
    assert interface_exists(context.netns, ifname=if_br0p0)
    assert interface_exists(context.netns, ifname=if_br0p1)
    assert address_exists(context.netns, ifname=if_br0, address=ifaddr1)
    assert address_exists(context.netns, ifname=if_br0, address=ifaddr2)
    assert route_exists(context.netns, gateway=router, dst=dst, dst_len=24)

    # remove the interface
    iface = context.ndb.interfaces[if_br0].remove().commit()

    assert not interface_exists(context.netns, ifname=if_br0)
    assert not address_exists(context.netns, ifname=if_br0, address=ifaddr1)
    assert not address_exists(context.netns, ifname=if_br0, address=ifaddr2)
    assert not route_exists(context.netns, gateway=router, dst=dst, dst_len=24)

    # revert the changes using the implicit last_save
    iface.rollback()
    assert interface_exists(context.netns, ifname=if_br0)
    assert interface_exists(context.netns, ifname=if_br0p0)
    assert interface_exists(context.netns, ifname=if_br0p1)
    assert address_exists(context.netns, ifname=if_br0, address=ifaddr1)
    assert address_exists(context.netns, ifname=if_br0, address=ifaddr2)
    assert route_exists(context.netns, gateway=router, dst=dst, dst_len=24)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_vlan_deps(context):
    if_host = context.new_ifname
    if_vlan = context.new_ifname
    ifaddr1 = context.new_ipaddr
    ifaddr2 = context.new_ipaddr
    router = context.new_ipaddr
    dst = str(context.ipnets[1].network)

    (
        context.ndb.interfaces.create(
            ifname=if_host, kind='dummy', state='up'
        ).commit()
    )

    (
        context.ndb.interfaces.create(
            ifname=if_vlan, kind='vlan', state='up', vlan_id=1001, link=if_host
        )
        .add_ip(address=ifaddr1, prefixlen=24)
        .add_ip(address=ifaddr2, prefixlen=24)
        .commit()
    )

    (context.ndb.routes.create(dst=dst, dst_len=24, gateway=router).commit())

    # check everything is in place
    assert interface_exists(context.netns, ifname=if_host)
    assert interface_exists(context.netns, ifname=if_vlan)
    assert address_exists(context.netns, ifname=if_vlan, address=ifaddr1)
    assert address_exists(context.netns, ifname=if_vlan, address=ifaddr2)
    assert route_exists(context.netns, dst=dst, gateway=router)

    # remove the interface
    iface = context.ndb.interfaces[if_host].remove().commit()

    # check there is no interface, no route
    assert not interface_exists(context.netns, ifname=if_host)
    assert not interface_exists(context.netns, ifname=if_vlan)
    assert not address_exists(context.netns, ifname=if_vlan, address=ifaddr1)
    assert not address_exists(context.netns, ifname=if_vlan, address=ifaddr2)
    assert not route_exists(context.netns, dst=dst, gateway=router)

    # revert the changes using the implicit last_save
    iface.rollback()
    assert interface_exists(context.netns, ifname=if_host)
    assert interface_exists(context.netns, ifname=if_vlan)
    assert address_exists(context.netns, ifname=if_vlan, address=ifaddr1)
    assert address_exists(context.netns, ifname=if_vlan, address=ifaddr2)
    assert route_exists(context.netns, dst=dst, gateway=router)
