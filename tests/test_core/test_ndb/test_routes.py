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
