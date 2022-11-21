import logging
import uuid

import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.marks import require_root
from pr2test.tools import address_exists, interface_exists

from pyroute2 import NDB, netns

pytestmark = [require_root()]

test_matrix = make_test_matrix(dbs=['sqlite3/:memory:', 'postgres/pr2test'])


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_create_remove(context):
    nsname = context.new_nsname
    with NDB(log=(context.new_log, logging.DEBUG)) as ndb:
        # create a netns via ndb.netns
        ndb.netns.create(nsname).commit()
        assert nsname in netns.listnetns()
        # remove the netns
        ndb.netns[nsname].remove().commit()
        assert nsname not in netns.listnetns()


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_views_contain(context):
    nsname = context.new_nsname
    v0 = context.new_ifname
    v1 = context.new_ifname

    context.ndb.sources.add(netns=nsname)
    context.ndb.interfaces.create(
        **{
            'ifname': v0,
            'kind': 'veth',
            'peer': {'ifname': v1, 'net_ns_fd': nsname},
        }
    ).commit()

    assert v0 in context.ndb.interfaces
    assert v1 in context.ndb.interfaces  # should be fixed?
    assert {'ifname': v0, 'target': 'localhost'} in context.ndb.interfaces
    assert {'ifname': v1, 'target': nsname} in context.ndb.interfaces


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_interface_move(context):
    ifname = context.new_ifname
    ifaddr = context.new_ipaddr
    nsname = context.new_nsname

    context.ndb.sources.add(netns=nsname)

    # create the interface
    (context.ndb.interfaces.create(ifname=ifname, kind='dummy').commit())

    # move it to a netns
    (context.ndb.interfaces[ifname].set('net_ns_fd', nsname).commit())

    # setup the interface only when it is moved
    (
        context.ndb.interfaces.wait(target=nsname, ifname=ifname)
        .set('state', 'up')
        .set('address', '00:11:22:33:44:55')
        .add_ip('%s/24' % ifaddr)
        .commit()
    )

    assert interface_exists(
        nsname, ifname=ifname, state='up', address='00:11:22:33:44:55'
    )


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_source_basic(context):
    ifname = context.new_ifname
    ifaddr1 = context.new_ipaddr
    ifaddr2 = context.new_ipaddr
    ifaddr3 = context.new_ipaddr
    nsname = context.new_nsname

    context.ndb.sources.add(netns=nsname)

    (
        context.ndb.interfaces.create(
            target=nsname, ifname=ifname, kind='dummy'
        )
        .ipaddr.create(address=ifaddr1, prefixlen=24)
        .create(address=ifaddr2, prefixlen=24)
        .create(address=ifaddr3, prefixlen=24)
        .commit()
    )

    with NDB(
        sources=[{'target': 'localhost', 'netns': nsname, 'kind': 'netns'}]
    ) as ndb:
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

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy')
        .add_ip(address=ipaddr, prefixlen=24)
        .commit()
    )

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

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy')
        .add_ip(address=ipaddr, prefixlen=24)
        .commit()
    )

    assert interface_exists(nsname, ifname=ifname)
    assert address_exists(nsname, ifname=ifname, address=ipaddr)
