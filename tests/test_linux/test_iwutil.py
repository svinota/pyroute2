import collections
import errno
from typing import Generator

import pytest
from pr2test.marks import require_root

from pyroute2 import IW, IPRoute
from pyroute2.netlink.exceptions import NetlinkError
from pyroute2.netlink.nl80211 import nl80211cmd

# FIXME: should be fixed after dropping support for Python 3.9
try:
    from types import NoneType
except ImportError:
    NoneType = type(None)

pytestmark = [require_root()]


@pytest.fixture
def ctx():
    iw = None
    ifname = None
    wiphy = None
    index = None
    try:
        iw = IW()
    except NetlinkError as e:
        if e.code == errno.ENOENT:
            pytest.skip('nl80211 not supported')
        raise
    ifaces = iw.get_interfaces_dump()
    if not ifaces:
        raise pytest.skip('no wireless interfaces found')
    for i in ifaces:
        ifname = i.get_attr('NL80211_ATTR_IFNAME')
        index = i.get_attr('NL80211_ATTR_IFINDEX')
        wiphy = i.get_attr('NL80211_ATTR_WIPHY')
        if index:
            break
    else:
        pytest.skip('can not detect the interface to use')

    yield collections.namedtuple(
        'WirelessContext', ['iw', 'ifname', 'index', 'wiphy']
    )(iw, ifname, index, wiphy)

    iw.close()


def test_list_wiphy(ctx):
    ctx.iw.list_wiphy()


def test_list_dev(ctx):
    ctx.iw.list_dev()


def test_scan(ctx):
    with IPRoute() as ipr:
        ipr.link('set', index=ctx.index, state='up')
    ctx.iw.scan(ctx.index)


def assert_dump(ctx, dump):
    assert len(dump) >= 1
    assert any(map(lambda x: x.get('ifindex') == ctx.index, dump))
    assert any(map(lambda x: x.get('wiphy') == ctx.wiphy, dump))


def test_get_interface_by_phy(ctx):
    dump = ctx.iw.get_interface_by_phy(ctx.wiphy)
    assert isinstance(dump, list)
    assert_dump(ctx, dump)


def test_get_interface_by_ifindex(ctx):
    dump = ctx.iw.get_interface_by_ifindex(ctx.index)
    assert isinstance(dump, list)
    assert_dump(ctx, dump)


def test_get_interfaces_dict(ctx):
    d = ctx.iw.get_interfaces_dict()
    assert isinstance(d, dict)
    for key, (index, name, address, freq, chan_width) in d.items():
        assert isinstance(key, (NoneType, str))
        assert isinstance(index, (NoneType, int))
        assert isinstance(name, str)
        assert isinstance(address, str) and all(
            map(lambda x: x >= 0, [int(x, 16) for x in address.split(':')])
        )
        assert isinstance(freq, int) and freq >= 0
        assert isinstance(chan_width, (NoneType, int))


def test_get_stations(ctx):
    dump = ctx.iw.get_stations(ctx.index)
    assert isinstance(dump, Generator)
    materialized = tuple(dump)
    assert len(materialized) >= 1
    sta_info = materialized[0].get('NL80211_ATTR_STA_INFO')
    assert isinstance(sta_info, nl80211cmd.STAInfo)
