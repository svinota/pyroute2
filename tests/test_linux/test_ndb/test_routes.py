import random
from functools import partial

import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.marks import require_root
from pr2test.tools import address_exists, interface_exists, route_exists

from pyroute2.ndb.objects.route import Metrics, MetricsStub
from pyroute2.netlink.rtnl.rtmsg import IP6_RT_PRIO_USER, rtmsg

pytestmark = [require_root()]


test_matrix_simple = make_test_matrix(
    targets=['local', 'netns'], dbs=['sqlite3/:memory:', 'postgres/pr2test']
)


@pytest.mark.parametrize('context', test_matrix_simple, indirect=True)
def test_table_undef(context):
    ipaddr1 = context.new_ip6addr
    ipaddr2 = context.new_ip6addr
    index, ifname = context.default_interface
    (
        context.ndb.routes.create(
            dst=ipaddr1, dst_len=128, table=5000, oif=index
        ).commit()
    )
    assert route_exists(context.netns, dst=ipaddr1, table=5000)
    assert not route_exists(context.netns, dst=ipaddr2, table=5000)
    assert context.ndb.routes[f'{ipaddr1}/128']['oif'] == index
    with pytest.raises(KeyError):
        context.ndb.routes[f'{ipaddr2}/128']


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
def test_ipv6_default_priority(context):
    ifname = context.new_ifname
    ipaddr = context.new_ip6addr
    table = context.table
    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(f'{ipaddr}/64')
        .commit()
    )
    dst = 'beef:feed:fade::'
    parameters = {
        'dst': f'{dst}/112',
        'oif': context.ndb.interfaces[ifname]['index'],
        'priority': 0,
        'table': table,
    }
    context.ndb.routes.create(**parameters).commit()
    assert route_exists(context.netns, dst=dst, table=table or 254)
    assert context.ndb.routes[parameters]['priority'] == IP6_RT_PRIO_USER


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_empty_target(context):
    ipaddr = context.new_ip6addr
    table = context.table
    index, ifname = context.default_interface
    (
        context.ndb.routes.create(
            dst=ipaddr, dst_len=128, oif=index, table=table
        ).commit()
    )
    assert route_exists(context.netns, dst=ipaddr, table=table or 254)
    (
        context.ndb.routes[{'table': table, 'dst': f'{ipaddr}/128'}]
        .remove()
        .commit()
    )
    assert not route_exists(context.netns, dst=ipaddr, table=table or 254)


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


def match_metrics(target, gateway, msg):
    if msg.get_attr('RTA_GATEWAY') != gateway:
        return False
    mtu = msg.get_attr('RTA_METRICS', rtmsg()).get_attr('RTAX_MTU', 0)
    return mtu == target


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
    assert address_exists(context.netns, ifname=ifname, address=ifaddr)
    assert route_exists(
        context.netns, match=partial(match_metrics, target, gateway2)
    )


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_metrics_set(context):
    index, ifname = context.default_interface
    ifaddr = context.new_ipaddr
    gateway = context.new_ipaddr
    ipnet = str(context.ipnets[1].network)
    target = 1280

    with context.ndb.interfaces[ifname] as dummy:
        dummy.add_ip(address=ifaddr, prefixlen=24)
        dummy.set(state='up')

    route = context.ndb.routes.create(dst=ipnet, dst_len=24, gateway=gateway)
    route.commit()

    assert route_exists(context.netns, dst=ipnet, dst_len=24, gateway=gateway)
    with pytest.raises(KeyError):
        assert route['metrics']['mtu']
    assert isinstance(route['metrics'].asyncore, MetricsStub)

    route['metrics']['mtu'] = target
    assert isinstance(route['metrics'].asyncore, Metrics)

    route.commit()
    assert route_exists(
        context.netns, match=partial(match_metrics, target, gateway)
    )


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
