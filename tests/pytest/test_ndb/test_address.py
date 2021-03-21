import pytest
from pr2test.tools import address_exists


@pytest.mark.parametrize('context', ['local', 'netns'], indirect=True)
def test_add_del_ip_dict(context):
    ifname = context.ifname
    ifaddr1 = context.ifaddr
    ifaddr2 = context.ifaddr

    (context
     .ndb
     .interfaces
     .create(ifname=ifname, kind='dummy', state='down')
     .add_ip({'address': ifaddr1, 'prefixlen': 24})
     .add_ip({'address': ifaddr2, 'prefixlen': 24})
     .commit())

    assert address_exists(context.netns, ifname=ifname, address=ifaddr1)
    assert address_exists(context.netns, ifname=ifname, address=ifaddr2)

    (context
     .ndb
     .interfaces[{'ifname': ifname}]
     .del_ip({'address': ifaddr2, 'prefixlen': 24})
     .del_ip({'address': ifaddr1, 'prefixlen': 24})
     .commit())

    assert not address_exists(context.netns, ifname=ifname, address=ifaddr1)
    assert not address_exists(context.netns, ifname=ifname, address=ifaddr2)


@pytest.mark.parametrize('context', ['local', 'netns'], indirect=True)
def test_add_del_ip_string(context):
    ifname = context.ifname
    ifaddr1 = '%s/24' % context.ifaddr
    ifaddr2 = '%s/24' % context.ifaddr

    (context
     .ndb
     .interfaces
     .create(ifname=ifname, kind='dummy', state='down')
     .add_ip(ifaddr1)
     .add_ip(ifaddr2)
     .commit())

    assert address_exists(context.netns, ifname=ifname, address=ifaddr1)
    assert address_exists(context.netns, ifname=ifname, address=ifaddr2)

    (context
     .ndb
     .interfaces[{'ifname': ifname}]
     .del_ip(ifaddr2)
     .del_ip(ifaddr1)
     .commit())

    assert not address_exists(context.netns, ifname=ifname, address=ifaddr1)
    assert not address_exists(context.netns, ifname=ifname, address=ifaddr2)
