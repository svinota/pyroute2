from socket import AF_INET, AF_INET6

import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.marks import require_root
from pr2test.tools import address_exists, interface_exists

pytestmark = [require_root()]
test_matrix = make_test_matrix(
    targets=['local', 'netns'], dbs=['sqlite3/:memory:', 'postgres/pr2test']
)


@pytest.mark.parametrize(
    'ipam,prefixlen', (('new_ipaddr', 24), ('new_ip6addr', 64))
)
@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_add_del_ip_dict(context, ipam, prefixlen):
    ifname = context.new_ifname
    ifaddr1 = getattr(context, ipam)
    ifaddr2 = getattr(context, ipam)

    (
        context.ndb.interfaces.create(
            ifname=ifname, kind='dummy', state='down'
        )
        .add_ip({'address': ifaddr1, 'prefixlen': prefixlen})
        .add_ip({'address': ifaddr2, 'prefixlen': prefixlen})
        .commit()
    )

    assert address_exists(context.netns, ifname=ifname, address=ifaddr1)
    assert address_exists(context.netns, ifname=ifname, address=ifaddr2)

    (
        context.ndb.interfaces[{'ifname': ifname}]
        .del_ip({'address': ifaddr2, 'prefixlen': prefixlen})
        .del_ip({'address': ifaddr1, 'prefixlen': prefixlen})
        .commit()
    )

    assert not address_exists(context.netns, ifname=ifname, address=ifaddr1)
    assert not address_exists(context.netns, ifname=ifname, address=ifaddr2)


@pytest.mark.parametrize(
    'ipam,prefixlen', (('new_ipaddr', 24), ('new_ip6addr', 64))
)
@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_add_del_ip_string(context, ipam, prefixlen):
    ifname = context.new_ifname
    ifaddr1 = f'{getattr(context, ipam)}/{prefixlen}'
    ifaddr2 = f'{getattr(context, ipam)}/{prefixlen}'

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


@pytest.mark.parametrize(
    'ipam,prefixlen,family',
    (('new_ipaddr', 24, AF_INET), ('new_ip6addr', 64, AF_INET6)),
)
@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_del_ip_match(context, ipam, prefixlen, family):
    ifname = context.new_ifname
    ipaddr1 = getattr(context, ipam)
    ipaddr2 = getattr(context, ipam)
    ipaddr3 = getattr(context, ipam)

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(address=ipaddr1, prefixlen=prefixlen)
        .add_ip(address=ipaddr2, prefixlen=prefixlen)
        .add_ip(address=ipaddr3, prefixlen=prefixlen)
        .commit()
    )

    assert address_exists(context.netns, ifname=ifname, address=ipaddr1)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr2)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr3)

    (context.ndb.interfaces[ifname].del_ip(family=family).commit())

    assert not address_exists(context.netns, ifname=ifname, address=ipaddr1)
    assert not address_exists(context.netns, ifname=ifname, address=ipaddr2)
    assert not address_exists(context.netns, ifname=ifname, address=ipaddr3)


@pytest.mark.parametrize(
    'ipam,prefixlen', (('new_ipaddr', 24), ('new_ip6addr', 64))
)
@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_del_ip_fail(context, ipam, prefixlen):
    ifname = context.new_ifname
    ipaddr = f'{getattr(context, ipam)}/{prefixlen}'
    ipaddr_fail = f'{getattr(context, ipam)}/{prefixlen}'

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(ipaddr)
        .commit()
    )

    assert interface_exists(context.netns, ifname=ifname)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr)

    with pytest.raises(KeyError):
        (context.ndb.interfaces[ifname].del_ip(ipaddr_fail).commit())

    assert interface_exists(context.netns, ifname=ifname)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr)


@pytest.mark.parametrize(
    'ipam,prefixlen', (('new_ipaddr', 24), ('new_ip6addr', 64))
)
@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_del_ip_match_fail(context, ipam, prefixlen):
    ifname = context.new_ifname
    ipaddr = getattr(context, ipam)
    ipaddr_fail = getattr(context, ipam)

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(address=ipaddr, prefixlen=prefixlen)
        .commit()
    )

    assert interface_exists(context.netns, ifname=ifname)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr)

    with pytest.raises(KeyError):
        (context.ndb.interfaces[ifname].del_ip(address=ipaddr_fail).commit())

    assert interface_exists(context.netns, ifname=ifname)
    assert address_exists(context.netns, ifname=ifname, address=ipaddr)
