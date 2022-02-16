import pytest
from socket import AF_INET
from pr2test.tools import address_exists
from pr2test.tools import interface_exists
from pr2test.context_manager import make_test_matrix


test_matrix = make_test_matrix(
    targets=['local', 'netns'], dbs=['sqlite3/:memory:', 'postgres/pr2test']
)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_add_del_ip_dict(context):
    ifname = context.new_ifname
    ifaddr1 = context.new_ipaddr
    ifaddr2 = context.new_ipaddr

    (
        context.ndb.interfaces.create(
            ifname=ifname, kind='dummy', state='down'
        )
        .add_ip({'address': ifaddr1, 'prefixlen': 24})
        .add_ip({'address': ifaddr2, 'prefixlen': 24})
        .commit()
    )

    assert address_exists(context.netns, ifname=ifname, address=ifaddr1)
    assert address_exists(context.netns, ifname=ifname, address=ifaddr2)

    (
        context.ndb.interfaces[{'ifname': ifname}]
        .del_ip({'address': ifaddr2, 'prefixlen': 24})
        .del_ip({'address': ifaddr1, 'prefixlen': 24})
        .commit()
    )

    assert not address_exists(context.netns, ifname=ifname, address=ifaddr1)
    assert not address_exists(context.netns, ifname=ifname, address=ifaddr2)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_add_del_ip_string(context):
    ifname = context.new_ifname
    ifaddr1 = '%s/24' % context.new_ipaddr
    ifaddr2 = '%s/24' % context.new_ipaddr

    (
        context.ndb.interfaces.create(
            ifname=ifname, kind='dummy', state='down'
        )
        .add_ip(ifaddr1)
        .add_ip(ifaddr2)
        .commit()
    )

    assert address_exists(context.netns, ifname=ifname, address=ifaddr1)
    assert address_exists(context.netns, ifname=ifname, address=ifaddr2)

    (
        context.ndb.interfaces[{'ifname': ifname}]
        .del_ip(ifaddr2)
        .del_ip(ifaddr1)
        .commit()
    )

    assert not address_exists(context.netns, ifname=ifname, address=ifaddr1)
    assert not address_exists(context.netns, ifname=ifname, address=ifaddr2)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_del_ip_match(context):
    ifname = context.new_ifname
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr
    ipaddr3 = context.new_ipaddr

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(address=ipaddr1, prefixlen=24)
        .add_ip(address=ipaddr2, prefixlen=24)
        .add_ip(address=ipaddr3, prefixlen=24)
        .commit()
    )

    assert address_exists(context.netns, ifname=ifname, address=ipaddr1)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr2)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr3)

    (context.ndb.interfaces[ifname].del_ip(family=AF_INET).commit())

    assert not address_exists(context.netns, ifname=ifname, address=ipaddr1)
    assert not address_exists(context.netns, ifname=ifname, address=ipaddr2)
    assert not address_exists(context.netns, ifname=ifname, address=ipaddr3)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_del_ip_fail(context):
    ifname = context.new_ifname
    ipaddr = '%s/24' % context.new_ipaddr
    ipaddr_fail = '%s/24' % context.new_ipaddr

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(ipaddr)
        .commit()
    )

    assert interface_exists(context.netns, ifname=ifname)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr)

    try:
        (context.ndb.interfaces[ifname].del_ip(ipaddr_fail).commit())
        raise Exception('shall not pass')
    except KeyError:
        pass

    assert interface_exists(context.netns, ifname=ifname)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_del_ip_match_fail(context):
    ifname = context.new_ifname
    ipaddr = context.new_ipaddr
    ipaddr_fail = context.new_ipaddr

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(address=ipaddr, prefixlen=24)
        .commit()
    )

    assert interface_exists(context.netns, ifname=ifname)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr)

    try:
        (context.ndb.interfaces[ifname].del_ip(address=ipaddr_fail).commit())
        raise Exception('shall not pass')
    except KeyError:
        pass

    assert interface_exists(context.netns, ifname=ifname)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr)
