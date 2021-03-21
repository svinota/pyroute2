from pyroute2 import NDB
from pr2test.tools import interface_exists


def test_move(context):
    ifname = context.ifname
    ifaddr = context.ifaddr
    nsname = context.nsname

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


def test_basic(context):
    ifname = context.ifname
    ifaddr1 = context.ifaddr
    ifaddr2 = context.ifaddr
    ifaddr3 = context.ifaddr
    nsname = context.nsname

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
