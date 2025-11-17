import pytest


def test_change_gw(ndb, test_link_ifname, sync_ipr):
    ipaddr = '10.1.2.3/24'
    dst = '10.2.1.0/24'
    gw0 = '10.1.2.4'
    gw1 = '10.1.2.5'
    ndb.interfaces[test_link_ifname].add_ip(ipaddr).commit()
    ndb.routes.create(dst=dst, gateway=gw0).commit()
    routes = sync_ipr.route('dump', dst=dst)
    assert len(routes) == 1
    assert routes[0].get('gateway') == gw0
    ndb.routes[dst].set('gateway', gw1).commit()
    routes = sync_ipr.route('dump', dst=dst)
    assert len(routes) == 1
    assert routes[0].get('gateway') == gw1


def test_add_default(ndb, test_link_ifname, sync_ipr):
    ipaddr = '10.1.2.3/24'
    gw0 = '10.1.2.4'
    ndb.interfaces[test_link_ifname].add_ip(ipaddr).commit()
    ndb.routes.create(gateway=gw0).commit()
    routes = sync_ipr.route('dump', gateway=gw0)
    assert len(routes) == 1


def test_change_default(ndb, test_link_ifname, sync_ipr):
    gw1 = '10.1.2.5'
    test_add_default(ndb, test_link_ifname, sync_ipr)
    ndb.routes['default'].set('gateway', gw1).commit()
    routes = sync_ipr.route('dump', gateway=gw1)
    assert len(routes) == 1


def test_gateway_warn(ndb, test_link_ifname, sync_ipr):
    '''Bug-Url: https://github.com/svinota/pyroute2/issues/1438'''
    ipaddr = '10.1.2.3/24'
    gw0 = '10.1.2.4'
    ndb.interfaces[test_link_ifname].add_ip(ipaddr).commit()
    with pytest.warns() as warnings:
        ndb.routes.create(gateway=f'{gw0}/24').commit()
    routes = sync_ipr.route('dump', gateway=gw0)
    assert len(routes) == 1
    assert len(warnings) == 1
    assert 'network mask' in str(warnings[0].message)


@pytest.mark.parametrize(
    'prio0,gw0,prio1,gw1',
    (
        (None, '10.1.2.4', 100, None),
        (0, '10.1.2.4', 200, None),
        (100, '10.1.2.4', 200, None),
        (None, '10.1.2.4', 100, '10.1.2.5'),
        (100, '10.1.2.4', 200, '10.1.2.5'),
        (100, '10.1.2.4', None, None),
        (100, '10.1.2.4', 0, None),
    ),
)
def test_change_add_remove(
    ndb, test_link_ifname, sync_ipr, prio0, gw0, prio1, gw1
):
    ipaddr = '10.1.2.3/24'
    ndb.interfaces[test_link_ifname].add_ip(ipaddr).commit()
    r0 = ndb.routes.create(gateway=gw0)
    if prio0 is not None:
        r0.set('priority', prio0)
    r0.commit()

    r1 = ndb.routes['default']
    if gw1 is not None:
        r1.set('gateway', gw1)
    if prio1 is not None:
        r1.set('priority', prio1)
    r1.commit()

    routes = tuple(sync_ipr.get_default_routes())
    assert len(routes) == 1
    assert routes[0].get('gateway') == gw1 or gw0
    assert routes[0].get('priority') == prio1 or (
        prio0 if prio0 is not None else 0
    )
