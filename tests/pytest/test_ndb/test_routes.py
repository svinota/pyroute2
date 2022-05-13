import random
import pytest
from pr2test.tools import route_exists
from pr2test.tools import address_exists
from pr2test.tools import interface_exists
from pr2test.context_manager import make_test_matrix
from pr2modules.netlink.rtnl.rtmsg import rtmsg


test_matrix_scopes = make_test_matrix(
    targets=['local', 'netns'],
    tables=[
        (None, 0),
        (None, 200),
        (None, 253),
        (6001, 0),
        (6001, 200),
        (6001, 253),
        (None, 'universe'),
        (None, 'site'),
        (None, 'link'),
        (6001, 'universe'),
        (6001, 'site'),
        (6001, 'link'),
    ],
    dbs=['sqlite3/:memory:', 'postgres/pr2test'],
)


@pytest.mark.parametrize('context', test_matrix_scopes, indirect=True)
def test_scopes(context):
    ipaddr = context.new_ipaddr
    ifname = context.new_ifname
    table, scope = context.table
    dst = '172.24.200.142'
    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(address=ipaddr, prefixlen=24)
        .commit()
    )
    spec = {
        'dst': dst,
        'oif': context.ndb.interfaces[ifname]['index'],
        'dst_len': 32,
        'scope': scope,
    }
    if table:
        spec['table'] = table
    (context.ndb.routes.create(**spec).commit())
    assert interface_exists(context.netns, ifname=ifname)
    assert route_exists(context.netns, **spec)
    (context.ndb.routes[spec].remove().commit())
    assert not route_exists(context.netns, **spec)


test_matrix_flags = make_test_matrix(
    targets=['local', 'netns'],
    tables=[
        (None, 0),
        (None, 4),
        (None, 'onlink'),
        (None, ['onlink']),
        (6001, 0),
        (6001, 4),
        (6001, 'onlink'),
        (6001, ['onlink']),
    ],
    dbs=['sqlite3/:memory:', 'postgres/pr2test'],
)


@pytest.mark.parametrize('context', test_matrix_flags, indirect=True)
def test_flags(context):
    ipaddr = context.new_ipaddr
    ifname = context.new_ifname
    table, flags = context.table
    dst = '172.24.200.142'
    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(address=ipaddr, prefixlen=24)
        .commit()
    )
    spec = {
        'dst': dst,
        'oif': context.ndb.interfaces[ifname]['index'],
        'dst_len': 32,
        'flags': flags,
        'gateway': context.new_ipaddr,
    }
    if table:
        spec['table'] = table
    (context.ndb.routes.create(**spec).commit())
    assert interface_exists(context.netns, ifname=ifname)
    assert route_exists(context.netns, **spec)
    (context.ndb.routes[spec].remove().commit())
    assert not route_exists(context.netns, **spec)


test_matrix = make_test_matrix(
    targets=['local', 'netns'],
    tables=[None, 501, 5001],
    dbs=['sqlite3/:memory:', 'postgres/pr2test'],
)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_basic(context):

    ifaddr = context.new_ipaddr
    router = context.new_ipaddr
    ifname = context.new_ifname
    ipnet = str(context.ipnets[1].network)
    table = context.table

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .ipaddr.create(address=ifaddr, prefixlen=24)
        .commit()
    )

    spec = {'dst_len': 24, 'dst': ipnet, 'gateway': router}

    if table:
        spec['table'] = table

    (context.ndb.routes.create(**spec).commit())

    assert interface_exists(context.netns, ifname=ifname)
    assert address_exists(context.netns, ifname=ifname, address=ifaddr)
    assert route_exists(context.netns, dst=ipnet, table=table or 254)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_default(context):

    ifaddr = context.new_ipaddr
    router = context.new_ipaddr
    ifname = context.new_ifname
    random.seed()
    tnum = random.randint(500, 600)

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip('%s/24' % ifaddr)
        .commit()
    )

    spec = {'dst': 'default', 'gateway': router}

    if context.table:
        table = context.table
    else:
        table = tnum
    spec['table'] = table

    (context.ndb.routes.create(**spec).commit())

    assert address_exists(context.netns, ifname=ifname, address=ifaddr)
    assert route_exists(context.netns, gateway=router, table=table)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_spec(context):

    ipaddr = context.new_ipaddr
    router = context.new_ipaddr
    ifname = context.new_ifname
    net = str(context.ipnets[1].network)
    table = context.table or 24000

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip('%s/24' % ipaddr)
        .commit()
    )

    (
        context.ndb.routes.create(
            table=table, dst='default', gateway=router
        ).commit()
    )

    (context.ndb.routes.create(dst=net, dst_len=24, gateway=router).commit())

    assert route_exists(context.netns, gateway=router, table=table)
    assert context.ndb.routes['default']  # !!! the system must have this
    assert context.ndb.routes[{'dst': 'default', 'table': table}]
    assert context.ndb.routes['%s/24' % net]
    assert context.ndb.routes[{'dst': net, 'dst_len': 24}]


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_multipath_ipv4(context):

    ifname = context.new_ifname
    ifaddr = context.new_ipaddr
    hop1 = context.new_ipaddr
    hop2 = context.new_ipaddr
    ipnet = str(context.ipnets[1].network)

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .ipaddr.create(address=ifaddr, prefixlen=24)
        .commit()
    )

    spec = {
        'dst_len': 24,
        'dst': ipnet,
        'multipath': [{'gateway': hop1}, {'gateway': hop2}],
    }

    if context.table:
        spec['table'] = context.table

    (context.ndb.routes.create(**spec).commit())

    def match_multipath(msg):
        if msg.get_attr('RTA_DST') != ipnet:
            return False
        gws_match = set((hop1, hop2))
        mp = msg.get_attr('RTA_MULTIPATH')
        if mp is None:
            return False
        gws_msg = set([x.get_attr('RTA_GATEWAY') for x in mp])
        return gws_match == gws_msg

    assert address_exists(context.netns, ifname=ifname, address=ifaddr)
    assert route_exists(context.netns, match=match_multipath)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_update_set(context):
    ifaddr = context.new_ipaddr
    router1 = context.new_ipaddr
    router2 = context.new_ipaddr
    ifname = context.new_ifname
    network = str(context.ipnets[1].network)

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .ipaddr.create(address=ifaddr, prefixlen=24)
        .commit()
    )

    spec = {'dst_len': 24, 'dst': network, 'gateway': router1}

    if context.table:
        spec['table'] = context.table

    r = context.ndb.routes.create(**spec).commit()

    assert address_exists(context.netns, ifname=ifname, address=ifaddr)
    assert route_exists(context.netns, dst=network, gateway=router1)

    r.set('gateway', router2).commit()

    assert route_exists(context.netns, dst=network, gateway=router2)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_update_replace(context):
    ifaddr = context.new_ipaddr
    router = context.new_ipaddr
    ifname = context.new_ifname
    network = str(context.ipnets[1].network)

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .ipaddr.create(address=ifaddr, prefixlen=24)
        .commit()
    )

    spec = {'dst_len': 24, 'dst': network, 'priority': 10, 'gateway': router}

    if context.table:
        spec['table'] = context.table

    (context.ndb.routes.create(**spec).commit())

    assert address_exists(context.netns, ifname=ifname, address=ifaddr)
    assert route_exists(context.netns, dst=network, priority=10)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_same_multipath(context):
    ifaddr = context.new_ipaddr
    gateway1 = context.new_ipaddr
    gateway2 = context.new_ipaddr
    ifname = context.new_ifname
    ipnet1 = str(context.ipnets[1].network)
    ipnet2 = str(context.ipnets[2].network)

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip({'address': ifaddr, 'prefixlen': 24})
        .commit()
    )

    # first route with these gateways
    (
        context.ndb.routes.create(
            dst=ipnet1,
            dst_len=24,
            multipath=[{'gateway': gateway1}, {'gateway': gateway2}],
        ).commit()
    )

    # second route with these gateways
    (
        context.ndb.routes.create(
            dst=ipnet2,
            dst_len=24,
            multipath=[{'gateway': gateway1}, {'gateway': gateway2}],
        ).commit()
    )

    def match_multipath(msg):
        if msg.get_attr('RTA_DST') != ipnet2:
            return False
        gws_match = set((gateway1, gateway2))
        mp = msg.get_attr('RTA_MULTIPATH')
        if mp is None:
            return False
        gws_msg = set([x.get_attr('RTA_GATEWAY') for x in mp])
        return gws_match == gws_msg

    assert address_exists(context.netns, ifname=ifname, address=ifaddr)
    assert route_exists(context.netns, match=match_multipath)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_same_metrics(context):
    ifaddr = context.new_ipaddr
    gateway1 = context.new_ipaddr
    gateway2 = context.new_ipaddr
    ifname = context.new_ifname
    ipnet1 = str(context.ipnets[1].network)
    ipnet2 = str(context.ipnets[2].network)
    target = 1300

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip({'address': ifaddr, 'prefixlen': 24})
        .commit()
    )

    # first route with these metrics
    (
        context.ndb.routes.create(
            dst=ipnet1, dst_len=24, gateway=gateway1, metrics={'mtu': target}
        ).commit()
    )

    # second route with these metrics
    (
        context.ndb.routes.create(
            dst=ipnet2, dst_len=24, gateway=gateway2, metrics={'mtu': target}
        ).commit()
    )

    # at this point it's already ok - otherwise the test
    # would explode on the second routes.create()
    # but lets double check

    def match_metrics(msg):
        if msg.get_attr('RTA_GATEWAY') != gateway2:
            return False
        mtu = msg.get_attr('RTA_METRICS', rtmsg()).get_attr('RTAX_MTU', 0)
        return mtu == target

    assert address_exists(context.netns, ifname=ifname, address=ifaddr)
    assert route_exists(context.netns, match=match_metrics)


def _test_metrics_update(context, method):

    ifaddr = context.new_ipaddr
    gateway1 = context.new_ipaddr
    ifname = context.new_ifname
    ipnet = str(context.ipnets[1].network)
    target = 1300
    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .ipaddr.create(address=ifaddr, prefixlen=24)
        .commit()
    )

    spec = {
        'dst_len': 24,
        'dst': ipnet,
        'gateway': gateway1,
        'metrics': {'mtu': target},
    }

    if context.table:
        spec['table'] = context.table

    (context.ndb.routes.create(**spec).commit())

    def match_metrics(msg):
        if msg.get_attr('RTA_GATEWAY') != gateway1:
            return False
        mtu = msg.get_attr('RTA_METRICS', rtmsg()).get_attr('RTAX_MTU', 0)
        return mtu == target

    assert address_exists(context.netns, ifname=ifname, address=ifaddr)
    assert route_exists(context.netns, match=match_metrics)

    target = 1500
    #
    # referencing the route via full spec instead of a
    # local variable is important here for the test
    # purposes: thus we check if the cache is working
    # properly and by the spec we hit the same object
    # every time
    context.ndb.routes[spec]['metrics']['mtu'] = target
    getattr(context.ndb.routes[spec], method)()

    assert route_exists(context.netns, match=match_metrics)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_metrics_update_apply(context):
    return _test_metrics_update(context, 'apply')


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_metrics_update_commit(context):
    return _test_metrics_update(context, 'commit')
