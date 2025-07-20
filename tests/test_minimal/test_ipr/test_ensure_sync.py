from net_tools import address_exists, interface_exists, route_exists


def test_ensure_link_present(sync_ipr, tmp_link_ifname, nsname):
    sync_ipr.ensure(
        sync_ipr.link,
        present=True,
        ifname=tmp_link_ifname,
        kind='dummy',
        state='up',
    )
    assert interface_exists(tmp_link_ifname, netns=nsname)
    sync_ipr.ensure(
        sync_ipr.link,
        present=True,
        ifname=tmp_link_ifname,
        kind='dummy',
        state='up',
    )


def test_ensure_link_absent(sync_ipr, nsname, test_link_ifname):
    sync_ipr.ensure(sync_ipr.link, present=False, ifname=test_link_ifname)
    assert not interface_exists(test_link_ifname, netns=nsname)
    sync_ipr.ensure(sync_ipr.link, present=False, ifname=test_link_ifname)


def test_ensure_address_exists(
    sync_ipr, nsname, test_link_index, test_link_ifname
):
    sync_ipr.ensure(
        sync_ipr.addr,
        present=True,
        index=test_link_index,
        address='192.168.145.150/24',
    )
    assert address_exists('192.168.145.150', test_link_ifname, netns=nsname)
    sync_ipr.ensure(
        sync_ipr.addr,
        present=True,
        index=test_link_index,
        address='192.168.145.150/24',
    )


def test_ensure_address_absent(
    sync_ipr, nsname, test_link_index, test_link_ifname
):
    sync_ipr.ensure(
        sync_ipr.addr,
        present=False,
        index=test_link_index,
        address='192.168.145.150/24',
    )
    assert not address_exists(
        '192.168.145.150', test_link_ifname, netns=nsname
    )
    sync_ipr.ensure(
        sync_ipr.addr,
        present=False,
        index=test_link_index,
        address='192.168.145.150/24',
    )


def test_ensure_route(sync_ipr, nsname, tmp_link_ifname):
    link = sync_ipr.ensure(
        sync_ipr.link,
        present=True,
        ifname=tmp_link_ifname,
        kind='dummy',
        state='up',
    )
    sync_ipr.ensure(
        sync_ipr.addr, present=True, index=link, address='192.168.145.150/24'
    )
    sync_ipr.ensure(
        sync_ipr.route,
        present=True,
        dst='10.20.30.0/24',
        gateway='192.168.145.151',
    )
    assert route_exists(dst='10.20.30.0/24', netns=nsname)
