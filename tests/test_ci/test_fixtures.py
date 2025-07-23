import pytest

from pyroute2.fixtures import iproute, ndb


def test_nsname_setup(nsname, cleanup_netns, netns_create_list):
    cleanup_netns.add(nsname)
    assert nsname in netns_create_list


def test_nsname_cleanup(cleanup_netns, netns_remove_list):
    assert cleanup_netns <= netns_remove_list


@pytest.mark.parametrize(
    'fixture,scope,name',
    (
        (iproute.async_context, 'function', 'async_context'),
        (iproute.async_ipr, 'function', 'async_ipr'),
        (iproute.nsname, 'function', 'nsname'),
        (iproute.setns_context, 'function', 'setns_context'),
        (iproute.sync_context, 'function', 'sync_context'),
        (iproute.sync_ipr, 'function', 'sync_ipr'),
        (iproute.test_link, 'function', 'test_link'),
        (iproute.test_link_address, 'function', 'test_link_address'),
        (iproute.test_link_ifinfmsg, 'function', 'test_link_ifinfmsg'),
        (iproute.test_link_ifname, 'function', 'test_link_ifname'),
        (iproute.test_link_index, 'function', 'test_link_index'),
        (ndb.ndb, 'function', 'ndb'),
    ),
    ids=(
        'async_context',
        'async_ipr',
        'ndb',
        'nsname',
        'setns_context',
        'sync_context',
        'sync_ipr',
        'test_link',
        'test_link_address',
        'test_link_ifinfmsg',
        'test_link_ifname',
        'test_link_index',
    ),
)
def test_fixture_spec(check_fixture_spec, fixture, scope, name):
    assert check_fixture_spec(fixture, scope=scope, name=name)


def test_chain(nsname, sync_ipr, async_ipr, test_link, ndb, netns_create_list):
    assert nsname == sync_ipr.status['netns']
    assert nsname == async_ipr.status['netns']
    assert nsname == test_link.netns
    assert (
        ndb.sources['localhost']
        .nl.status['netns']
        .decode('utf-8')
        .endswith(nsname)
    )
    assert nsname in netns_create_list
