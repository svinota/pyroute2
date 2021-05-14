import uuid
import pytest
from pyroute2 import NDB
from pr2test.tools import interface_exists
from pr2test.tools import address_exists
from pr2test.context_manager import make_test_matrix


test_matrix = make_test_matrix(dbs=['sqlite3/:memory:', 'postgres/pr2test'])


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_move(context):
    ifname = context.new_ifname
    ifaddr = context.new_ipaddr
    nsname = context.new_nsname

    context.ndb.sources.add(netns=nsname)

    # create the interface
    (context
     .ndb
     .interfaces
     .create(ifname=ifname, kind='dummy')
     .commit())

    # move it to a netns
    (context
     .ndb
     .interfaces[ifname]
     .set('net_ns_fd', nsname)
     .commit())

    # setup the interface only when it is moved
    (context
     .ndb
     .interfaces
     .wait(target=nsname, ifname=ifname)
     .set('state', 'up')
     .set('address', '00:11:22:33:44:55')
     .add_ip('%s/24' % ifaddr)
     .commit())

    assert interface_exists(nsname,
                            ifname=ifname,
                            state='up',
                            address='00:11:22:33:44:55')


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_basic(context):
    ifname = context.new_ifname
    ifaddr1 = context.new_ipaddr
    ifaddr2 = context.new_ipaddr
    ifaddr3 = context.new_ipaddr
    nsname = context.new_nsname

    context.ndb.sources.add(netns=nsname)

    (context
     .ndb
     .interfaces
     .create(target=nsname, ifname=ifname, kind='dummy')
     .ipaddr
     .create(address=ifaddr1, prefixlen=24)
     .create(address=ifaddr2, prefixlen=24)
     .create(address=ifaddr3, prefixlen=24)
     .commit())

    with NDB(sources=[{'target': 'localhost',
                       'netns': nsname,
                       'kind': 'netns'}]) as ndb:
        if_idx = ndb.interfaces[ifname]['index']
        addr1_idx = ndb.addresses['%s/24' % ifaddr1]['index']
        addr2_idx = ndb.addresses['%s/24' % ifaddr2]['index']
        addr3_idx = ndb.addresses['%s/24' % ifaddr3]['index']

    assert if_idx == addr1_idx == addr2_idx == addr3_idx


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_localhost_implicit(context):
    ifname = context.new_ifname
    ipaddr = context.new_ipaddr
    nsname = context.new_nsname

    context.ndb.sources.add(netns=nsname)
    context.ndb.localhost = nsname

    (context
     .ndb
     .interfaces
     .create(ifname=ifname, kind='dummy')
     .add_ip(address=ipaddr, prefixlen=24)
     .commit())

    assert interface_exists(nsname, ifname=ifname)
    assert address_exists(nsname, ifname=ifname, address=ipaddr)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_localhost_explicit(context):
    ifname = context.new_ifname
    ipaddr = context.new_ipaddr
    nsname = context.new_nsname
    target = str(uuid.uuid4())

    context.ndb.sources.add(netns=nsname, target=target)
    context.ndb.localhost = target

    (context
     .ndb
     .interfaces
     .create(ifname=ifname, kind='dummy')
     .add_ip(address=ipaddr, prefixlen=24)
     .commit())

    assert interface_exists(nsname, ifname=ifname)
    assert address_exists(nsname, ifname=ifname, address=ipaddr)
