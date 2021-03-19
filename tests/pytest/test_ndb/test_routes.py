import random
import pytest
from pr2test.tools import route_exists
from pr2test.tools import address_exists
from pr2test.tools import interface_exists
from pyroute2.netlink.rtnl.rtmsg import rtmsg


@pytest.mark.parametrize('context',
                         [('local', None),
                          ('local', 501),
                          ('local', 5001),
                          ('netns', None),
                          ('netns', 501),
                          ('netns', 5001)], indirect=True)
def test_basic(context):

    ifaddr = context.ifaddr
    router = context.ifaddr
    ifname = context.ifname
    ipnet = str(context.ipnets[1].network)
    table = context.table

    (context
     .ndb
     .interfaces
     .create(ifname=ifname, kind='dummy', state='up')
     .ipaddr
     .create(address=ifaddr, prefixlen=24)
     .commit())

    spec = {'dst_len': 24,
            'dst': ipnet,
            'gateway': router}

    if table:
        spec['table'] = table

    (context
     .ndb
     .routes
     .create(**spec)
     .commit())

    assert interface_exists(ifname, context.netns)
    assert address_exists(ifname, context.netns, address=ifaddr)
    assert route_exists(context.netns, dst=ipnet, table=table or 254)


@pytest.mark.parametrize('context',
                         [('local', None),
                          ('local', 501),
                          ('local', 5001),
                          ('netns', None),
                          ('netns', 501),
                          ('netns', 5001)], indirect=True)
def test_default(context):

    ifaddr = context.ifaddr
    router = context.ifaddr
    ifname = context.ifname
    random.seed()
    tnum = random.randint(500, 600)

    (context
     .ndb
     .interfaces
     .create(ifname=ifname, kind='dummy', state='up')
     .add_ip('%s/24' % ifaddr)
     .commit())

    spec = {'dst': 'default',
            'gateway': router}

    if context.table:
        table = context.table
    else:
        table = tnum
    spec['table'] = table

    (context
     .ndb
     .routes
     .create(**spec)
     .commit())

    assert address_exists(ifname, context.netns, address=ifaddr)
    assert route_exists(context.netns, gateway=router, table=table)


@pytest.mark.parametrize('context',
                         [('local', None),
                          ('local', 501),
                          ('local', 5001),
                          ('netns', None),
                          ('netns', 501),
                          ('netns', 5001)], indirect=True)
def test_multipath_ipv4(context):

    ifname = context.ifname
    ifaddr = context.ifaddr
    hop1 = context.ifaddr
    hop2 = context.ifaddr
    ipnet = str(context.ipnets[1].network)

    (context
     .ndb
     .interfaces
     .create(ifname=ifname, kind='dummy', state='up')
     .ipaddr
     .create(address=ifaddr, prefixlen=24)
     .commit())

    spec = {'dst_len': 24,
            'dst': ipnet,
            'multipath': [{'gateway': hop1},
                          {'gateway': hop2}]}

    if context.table:
        spec['table'] = context.table

    (context
     .ndb
     .routes
     .create(**spec)
     .commit())

    def match_multipath(msg):
        if msg.get_attr('RTA_DST') != ipnet:
            return False
        gws_match = set((hop1, hop2))
        mp = msg.get_attr('RTA_MULTIPATH')
        if mp is None:
            return False
        gws_msg = set([x.get_attr('RTA_GATEWAY') for x in mp])
        return gws_match == gws_msg

    assert address_exists(ifname, context.netns, address=ifaddr)
    assert route_exists(context.netns, match=match_multipath)


@pytest.mark.parametrize('context',
                         [('local', None),
                          ('local', 501),
                          ('local', 5001),
                          ('netns', None),
                          ('netns', 501),
                          ('netns', 5001)], indirect=True)
def test_update_set(context):
    ifaddr = context.ifaddr
    router1 = context.ifaddr
    router2 = context.ifaddr
    ifname = context.ifname
    network = str(context.ipnets[1].network)

    (context
     .ndb
     .interfaces
     .create(ifname=ifname, kind='dummy', state='up')
     .ipaddr
     .create(address=ifaddr, prefixlen=24)
     .commit())

    spec = {'dst_len': 24,
            'dst': network,
            'gateway': router1}

    if context.table:
        spec['table'] = context.table

    r = (context
         .ndb
         .routes
         .create(**spec)
         .commit())

    assert address_exists(ifname, context.netns, address=ifaddr)
    assert route_exists(context.netns, dst=network, gateway=router1)

    r.set('gateway', router2).commit()

    assert route_exists(context.netns, dst=network, gateway=router2)


@pytest.mark.parametrize('context',
                         [('local', None),
                          ('local', 501),
                          ('local', 5001),
                          ('netns', None),
                          ('netns', 501),
                          ('netns', 5001)], indirect=True)
def test_update_replace(context):
    ifaddr = context.ifaddr
    router = context.ifaddr
    ifname = context.ifname
    network = str(context.ipnets[1].network)

    (context
     .ndb
     .interfaces
     .create(ifname=ifname, kind='dummy', state='up')
     .ipaddr
     .create(address=ifaddr, prefixlen=24)
     .commit())

    spec = {'dst_len': 24,
            'dst': network,
            'priority': 10,
            'gateway': router}

    if context.table:
        spec['table'] = context.table

    (context
     .ndb
     .routes
     .create(**spec)
     .commit())

    assert address_exists(ifname, context.netns, address=ifaddr)
    assert route_exists(context.netns, dst=network, priority=10)


def _test_metrics_update(context, method):

    ifaddr = context.ifaddr
    gateway1 = context.ifaddr
    ifname = context.ifname
    ipnet = str(context.ipnets[1].network)
    target = 1300
    (context
     .ndb
     .interfaces
     .create(ifname=ifname, kind='dummy', state='up')
     .ipaddr
     .create(address=ifaddr, prefixlen=24)
     .commit())

    spec = {'dst_len': 24,
            'dst': ipnet,
            'gateway': gateway1,
            'metrics': {'mtu': target}}

    if context.table:
        spec['table'] = context.table

    r = (context
         .ndb
         .routes
         .create(**spec)
         .commit())

    def match_metrics(msg):
        if msg.get_attr('RTA_GATEWAY') != gateway1:
            return False
        mtu = (msg
               .get_attr('RTA_METRICS', rtmsg())
               .get_attr('RTAX_MTU', 0))
        return mtu == target

    assert address_exists(ifname, context.netns, address=ifaddr)
    assert route_exists(context.netns, match=match_metrics)

    target = 1500
    r['metrics']['mtu'] = target
    getattr(r, method)()

    assert route_exists(context.netns, match=match_metrics)


@pytest.mark.parametrize('context',
                         [('local', None),
                          ('local', 501),
                          ('local', 5001),
                          ('netns', None),
                          ('netns', 501),
                          ('netns', 5001)], indirect=True)
def test_metrics_update_apply(context):
    return _test_metrics_update(context, 'apply')


@pytest.mark.parametrize('context',
                         [('local', None),
                          ('local', 501),
                          ('local', 5001),
                          ('netns', None),
                          ('netns', 501),
                          ('netns', 5001)], indirect=True)
def test_metrics_update_commit(context):
    return _test_metrics_update(context, 'commit')
